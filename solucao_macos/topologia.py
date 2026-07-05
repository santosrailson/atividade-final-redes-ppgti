#!/usr/bin/env python3
"""
Topologia da rede de transporte 5G emulada com Mininet + Open vSwitch.

Representa os "4 roteadores da rede de transporte" pedidos no
enunciado do projeto como 4 switches OVS em linha:

    h_urllc_a --\\                                    /-- h_urllc_b
                 r1 ---- r2 ---- r3 ---- r4
    h_embb_a  --/                                    \\-- h_embb_b

Todos os hosts estão no mesmo domínio L2 (rede 10.0.0.0/16), então os
switches funcionam como switches "normais" (aprendizado de MAC) e não
precisamos de roteamento L3 dentro do Mininet. A diferenciação de
classe de tráfego (uRLLC vs eMBB) é feita inteiramente via QoS/filas
do OpenFlow, não por rotas diferentes.

Adaptação para macOS: o OVSSwitch é criado com datapath="user", ou
seja, o encaminhamento de pacotes roda em userspace (processo
ovs-vswitchd) em vez do módulo de kernel openvswitch.ko. Isso é
necessário porque, dentro do container Docker usado no macOS, o
kernel da VM do Docker Desktop normalmente não tem esse módulo
carregado. As regras de QoS (tc/HTB) continuam funcionando
normalmente, pois atuam diretamente nas interfaces de rede (veth),
independente do tipo de datapath do OVS.
"""

import os
import subprocess

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def configurar_interfaces_hosts(rede):
    """Desativa IPv6 e desliga offload de checksum em todas as interfaces.

    O offload de checksum feito pela NIC (real ou virtual) pode
    interferir na captura/injeção de pacotes crus feita pelo Scapy,
    então preferimos calcular os checksums em software.
    """
    for no in rede.hosts + rede.switches:
        no.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        no.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        no.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        for nome_interface in no.intfNames():
            if nome_interface != "lo":
                no.cmd("sysctl -w net.ipv6.conf.%s.disable_ipv6=1" % nome_interface)
                no.cmd("ethtool -K %s tx-checksum-ip-generic off 2>/dev/null" % nome_interface)
                no.cmd("ethtool -K %s rx-checksum off 2>/dev/null" % nome_interface)


def configurar_qos_ovs(switch, interface):
    """Cria, em cada porta do switch, duas filas HTB (Hierarchical Token Bucket):

    - Fila 0: prioridade normal (tráfego eMBB e demais fluxos).
    - Fila 1: alta prioridade, com min-rate elevado, reservada ao uRLLC.

    O "min-rate" da fila 1 garante banda mínima garantida para o
    tráfego sensível à latência mesmo quando o link está congestionado
    pelo eMBB.
    """
    switch.cmd(
        "ovs-vsctl -- set port %s qos=@newqos "
        "-- --id=@newqos create QoS type=linux-htb other-config:max-rate=1000000000 "
        "queues=0=@q0,1=@q1 "
        "-- --id=@q0 create Queue other-config:min-rate=1000000 other-config:max-rate=1000000000 "
        "-- --id=@q1 create Queue other-config:min-rate=500000000 other-config:max-rate=1000000000" %
        interface
    )


def configurar_ovs(switch):
    """Sobe as interfaces do switch e instala as regras OpenFlow de QoS.

    O switch continua se comportando como um switch L2 "normal"
    (aprendizado automático de MAC via ação `normal`); as regras
    apenas marcam qual fila de saída cada pacote deve usar:

    - TCP porta 5000 (uRLLC)      -> fila 1 (alta prioridade)
    - Qualquer outro tráfego       -> fila 0 (prioridade normal / eMBB)
    """
    info("*** Configurando OVS %s\n" % switch.name)

    switch.cmd("ip link set %s up" % switch.name)
    interfaces = [nome for nome in switch.intfNames() if nome != "lo"]
    for nome_interface in interfaces:
        switch.cmd("ip link set %s up" % nome_interface)

    ofctl = "ovs-ofctl -O OpenFlow13"
    switch.cmd("%s del-flows %s" % (ofctl, switch.name))

    switch.cmd(
        "%s add-flow %s 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
    )
    switch.cmd(
        "%s add-flow %s 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
    )
    switch.cmd(
        "%s add-flow %s 'priority=10,actions=set_queue:0,normal'" % (ofctl, switch.name)
    )

    for nome_interface in interfaces:
        configurar_qos_ovs(switch, nome_interface)


def limpar_ambiente():
    """Remove resíduos de execuções anteriores (bridges OVS, interfaces veth).

    Útil quando um experimento anterior não foi finalizado corretamente
    (ex.: container reiniciado no meio de um teste).
    """
    info("*** Limpando ambiente Mininet/OVS residual\n")
    os.system("mn -c 2>/dev/null")
    for nome_bridge in ["r1", "r2", "r3", "r4"]:
        os.system("ovs-vsctl --if-exists del-br %s 2>/dev/null" % nome_bridge)
    padrao_interfaces = "r[1-4]-eth|h_[a-z_]+-eth"
    try:
        saida = subprocess.check_output(
            "ip -o link show | awk -F': ' '{print $2}' | grep -E '^(%s)'" % padrao_interfaces,
            shell=True, text=True
        )
        for interface in saida.splitlines():
            interface = interface.strip()
            if interface:
                os.system("ip link del %s 2>/dev/null" % interface)
    except subprocess.CalledProcessError:
        pass


def criar_topologia():
    """Monta a topologia completa (hosts + 4 switches OVS) e devolve a rede pronta para uso."""
    limpar_ambiente()
    rede = Mininet(link=TCLink, switch=OVSSwitch)

    info("*** Criando hosts\n")
    host_urllc_a = rede.addHost("h_urllc_a", ip="10.0.1.1/16", mac="00:00:00:00:01:01")
    host_embb_a  = rede.addHost("h_embb_a",  ip="10.0.2.1/16", mac="00:00:00:00:02:01")
    host_urllc_b = rede.addHost("h_urllc_b", ip="10.0.3.2/16", mac="00:00:00:00:03:02")
    host_embb_b  = rede.addHost("h_embb_b",  ip="10.0.4.2/16", mac="00:00:00:00:04:02")

    info("*** Criando switches OVS (4 roteadores da rede de transporte)\n")
    r1 = rede.addSwitch("r1", cls=OVSSwitch, protocols="OpenFlow13", datapath="user")
    r2 = rede.addSwitch("r2", cls=OVSSwitch, protocols="OpenFlow13", datapath="user")
    r3 = rede.addSwitch("r3", cls=OVSSwitch, protocols="OpenFlow13", datapath="user")
    r4 = rede.addSwitch("r4", cls=OVSSwitch, protocols="OpenFlow13", datapath="user")

    info("*** Criando links\n")
    rede.addLink(host_urllc_a, r1, bw=100, delay="0ms")
    rede.addLink(host_embb_a,  r1, bw=100, delay="0ms")
    rede.addLink(r1, r2, bw=1000, delay="0ms")
    rede.addLink(r2, r3, bw=1000, delay="0ms")
    rede.addLink(r3, r4, bw=1000, delay="0ms")
    rede.addLink(r4, host_urllc_b, bw=100, delay="0ms")
    rede.addLink(r4, host_embb_b,  bw=100, delay="0ms")

    info("*** Iniciando rede\n")
    rede.start()

    configurar_interfaces_hosts(rede)

    info("*** Configurando switches OVS\n")
    for nome in ["r1", "r2", "r3", "r4"]:
        configurar_ovs(rede.getNodeByName(nome))

    return rede


def testar_conectividade(rede):
    info("*** Testando conectividade uRLLC (h_urllc_a -> h_urllc_b)\n")
    resultado = rede.getNodeByName("h_urllc_a").cmd("ping -c 4 -4 10.0.3.2")
    info(resultado)


if __name__ == "__main__":
    # Execução standalone: sobe a topologia e abre a CLI do Mininet
    # para inspeção manual (útil para depuração / demonstração).
    setLogLevel("info")
    rede = criar_topologia()
    testar_conectividade(rede)

    info("*** Abrindo interface de linha de comando do Mininet\n")
    CLI(rede)

    info("*** Parando rede\n")
    rede.stop()
