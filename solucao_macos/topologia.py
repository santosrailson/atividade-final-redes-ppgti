#!/usr/bin/env python3
"""
Topologia da rede de transporte 5G emulada com Mininet + Open vSwitch.

Cenário: monitoramento de segurança/incêndio de um campus universitário.
Três "ambientes" (prédios) do campus enviam tráfego uRLLC (alertas de
sensores de incêndio/fumaça) e eMBB (streaming das câmeras de vigilância)
através da rede de transporte (4 switches em linha) até uma Central de
Monitoramento único, que representa o NOC (Network Operations Center) do
campus:

    h_sensor_biblioteca --\\                                  /-- h_central_urllc
    h_cam_biblioteca    --/-- r1                              |
                                \\                             |
    h_sensor_labs        --\\    r2 ---- r3 ---- r4 -----------|
    h_cam_labs           --/---/                               |
                                                                 \\
    h_sensor_reitoria    --\\                                    \\-- h_central_video
    h_cam_reitoria       --/-- r3 (acima)

(cada prédio se conecta a um switch diferente da rede de transporte,
simulando pontos de acesso distintos espalhados pelo campus; a central
fica no switch mais distante, r4)

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

# Cada site do campus tem um sensor uRLLC (alerta de incêndio/fumaça) e
# uma câmera eMBB (vigilância), conectados ao switch indicado. IPs e
# MACs seguem o padrão <bloco>.<host>, um bloco /24 por site dentro da
# rede /16 compartilhada.
#  Nomes de host curtos de propósito: o Linux limita nomes de interface
#  a 15 caracteres (`<hostname>-ethN`), e "h_sensor_biblioteca-eth0"
#  (24 caracteres) estoura esse limite.
SITES = [
    {
        "nome": "biblioteca",
        "switch": "r1",
        "sensor": ("sens_bib", "10.0.11.1/16", "00:00:00:00:11:01"),
        "camera": ("cam_bib", "10.0.12.1/16", "00:00:00:00:12:01"),
    },
    {
        "nome": "labs",
        "switch": "r2",
        "sensor": ("sens_lab", "10.0.21.1/16", "00:00:00:00:21:01"),
        "camera": ("cam_lab", "10.0.22.1/16", "00:00:00:00:22:01"),
    },
    {
        "nome": "reitoria",
        "switch": "r3",
        "sensor": ("sens_rei", "10.0.31.1/16", "00:00:00:00:31:01"),
        "camera": ("cam_rei", "10.0.32.1/16", "00:00:00:00:32:01"),
    },
]

# Central de Monitoramento do campus (NOC), conectada ao switch mais
# distante da linha (r4) -- recebe tanto os alertas uRLLC quanto os
# streams de vídeo eMBB de todos os sites.
HOST_CENTRAL_URLLC = ("c_urllc", "10.0.99.1/16", "00:00:00:00:99:01")
HOST_CENTRAL_VIDEO = ("c_video", "10.0.99.2/16", "00:00:00:00:99:02")


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


TAXA_BACKBONE_MBPS = 20
TAXA_EMBB_NORMAL_BPS = 20000000
TAXA_EMBB_PROTEGIDA_BPS = 2000000


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
        "-- --id=@newqos create QoS type=linux-htb other-config:max-rate=20000000 "
        "queues=0=@q0,1=@q1 "
        "-- --id=@q0 create Queue external_ids:classe=embb other-config:min-rate=1000000 other-config:max-rate=20000000 "
        "-- --id=@q1 create Queue external_ids:classe=urllc other-config:min-rate=15000000 other-config:max-rate=20000000" %
        interface
    )


def configurar_ovs(switch, qos_estatico=True):
    """Sobe as interfaces do switch e instala as regras OpenFlow de QoS.

    O switch continua se comportando como um switch L2 "normal"
    (aprendizado automático de MAC via ação `normal`); as regras
    apenas marcam qual fila de saída cada pacote deve usar:

    - TCP porta 5000 (uRLLC)      -> fila 1 (alta prioridade)
    - Qualquer outro tráfego       -> fila 0 (prioridade normal / eMBB)

    Essas regras são as mesmas nos 4 switches, independente de qual
    site (prédio do campus) estiver conectado a cada um -- a
    priorização é por classe de tráfego (porta), não por origem.
    """
    info("*** Configurando OVS %s\n" % switch.name)

    switch.cmd("ip link set %s up" % switch.name)
    interfaces = [nome for nome in switch.intfNames() if nome != "lo"]
    for nome_interface in interfaces:
        switch.cmd("ip link set %s up" % nome_interface)

    ofctl = "ovs-ofctl -O OpenFlow13"
    switch.cmd("%s del-flows %s" % (ofctl, switch.name))

    if qos_estatico:
        switch.cmd(
            "%s add-flow %s 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
        )
        switch.cmd(
            "%s add-flow %s 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
        )
        switch.cmd("%s add-flow %s 'priority=10,actions=set_queue:0,normal'" % (ofctl, switch.name))
        for nome_interface in interfaces:
            configurar_qos_ovs(switch, nome_interface)
    else:
        switch.cmd("%s add-flow %s 'priority=10,actions=normal'" % (ofctl, switch.name))


def limpar_ambiente():
    """Remove resíduos de execuções anteriores (bridges OVS, interfaces veth).

    Útil quando um experimento anterior não foi finalizado corretamente
    (ex.: container reiniciado no meio de um teste).
    """
    info("*** Limpando ambiente Mininet/OVS residual\n")
    os.system("mn -c 2>/dev/null")
    for nome_bridge in ["r1", "r2", "r3", "r4"]:
        os.system("ovs-vsctl --if-exists del-br %s 2>/dev/null" % nome_bridge)
    os.system("ovs-vsctl -- --all destroy QoS -- --all destroy Queue 2>/dev/null")
    padrao_interfaces = "r[1-4]-eth|(sens|cam)_[a-z]+-eth|c_(urllc|video)-eth"
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


def criar_topologia(qos_estatico=True, taxa_backbone_mbps=TAXA_BACKBONE_MBPS):
    """Monta a topologia completa (hosts dos 3 sites do campus + central +
    4 switches OVS) e devolve a rede pronta para uso."""
    limpar_ambiente()
    # ARP estático evita que a descoberta de vizinhos concorra com o eMBB
    # justamente durante a saturação usada para avaliar o plano de dados.
    rede = Mininet(link=TCLink, switch=OVSSwitch, autoStaticArp=True)

    info("*** Criando switches OVS (4 roteadores da rede de transporte)\n")
    switches = {}
    for nome in ["r1", "r2", "r3", "r4"]:
        switches[nome] = rede.addSwitch(nome, cls=OVSSwitch, protocols="OpenFlow13", datapath="user")

    info("*** Criando hosts dos sites do campus (sensor + câmera por prédio)\n")
    for site in SITES:
        nome_sensor, ip_sensor, mac_sensor = site["sensor"]
        nome_camera, ip_camera, mac_camera = site["camera"]
        host_sensor = rede.addHost(nome_sensor, ip=ip_sensor, mac=mac_sensor)
        host_camera = rede.addHost(nome_camera, ip=ip_camera, mac=mac_camera)
        switch_site = switches[site["switch"]]
        rede.addLink(host_sensor, switch_site, bw=100, delay="0ms")
        rede.addLink(host_camera, switch_site, bw=100, delay="0ms")

    info("*** Criando host da Central de Monitoramento (NOC)\n")
    nome_urllc, ip_urllc, mac_urllc = HOST_CENTRAL_URLLC
    nome_video, ip_video, mac_video = HOST_CENTRAL_VIDEO
    host_central_urllc = rede.addHost(nome_urllc, ip=ip_urllc, mac=mac_urllc)
    host_central_video = rede.addHost(nome_video, ip=ip_video, mac=mac_video)
    rede.addLink(host_central_urllc, switches["r4"], bw=100, delay="0ms")
    rede.addLink(host_central_video, switches["r4"], bw=100, delay="0ms")

    info("*** Criando backbone da rede de transporte (r1-r2-r3-r4)\n")
    rede.addLink(switches["r1"], switches["r2"], bw=taxa_backbone_mbps, delay="1ms", max_queue_size=100)
    rede.addLink(switches["r2"], switches["r3"], bw=taxa_backbone_mbps, delay="1ms", max_queue_size=100)
    rede.addLink(switches["r3"], switches["r4"], bw=taxa_backbone_mbps, delay="1ms", max_queue_size=100)

    info("*** Iniciando rede\n")
    rede.start()

    configurar_interfaces_hosts(rede)

    info("*** Configurando switches OVS\n")
    for nome in ["r1", "r2", "r3", "r4"]:
        configurar_ovs(rede.getNodeByName(nome), qos_estatico=qos_estatico)

    return rede


def testar_conectividade(rede):
    ip_central = HOST_CENTRAL_URLLC[1].split("/")[0]
    for site in SITES:
        nome_sensor = site["sensor"][0]
        info("*** Testando conectividade uRLLC (%s -> central)\n" % nome_sensor)
        resultado = rede.getNodeByName(nome_sensor).cmd("ping -c 2 -4 %s" % ip_central)
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
