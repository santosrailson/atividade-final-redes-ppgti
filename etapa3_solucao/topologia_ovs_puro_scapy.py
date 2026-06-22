#!/usr/bin/env python3
"""
Topologia OVS puro (4 switches em linha) para uRLLC com Scapy/TCP.

Todos os roteadores da rede de transporte sao switches OVS.
A rede e um unico dominio L2 (/16) para evitar roteamento L3 nos switches.
A priorizacao do uRLLC e feita via QoS/filas OpenFlow.
"""

import os
import subprocess
import sys
import time

from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def configurar_interfaces_hosts(rede):
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
    switch.cmd(
        "ovs-vsctl -- set port %s qos=@newqos "
        "-- --id=@newqos create QoS type=linux-htb other-config:max-rate=1000000000 "
        "queues=0=@q0,1=@q1 "
        "-- --id=@q0 create Queue other-config:min-rate=1000000 other-config:max-rate=1000000000 "
        "-- --id=@q1 create Queue other-config:min-rate=500000000 other-config:max-rate=1000000000" %
        interface
    )


def configurar_ovs(switch):
    info("*** Configurando OVS %s\n" % switch.name)

    switch.cmd("ip link set %s up" % switch.name)
    interfaces = [nome for nome in switch.intfNames() if nome != "lo"]
    for nome_interface in interfaces:
        switch.cmd("ip link set %s up" % nome_interface)

    ofctl = "ovs-ofctl -O OpenFlow13"
    switch.cmd("%s del-flows %s" % (ofctl, switch.name))

    # OVS funciona como L2 learning switch (normal). Regras apenas para QoS.
    # uRLLC (porta 5000 TCP) -> fila 1 (alta prioridade)
    switch.cmd(
        "%s add-flow %s 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
    )
    switch.cmd(
        "%s add-flow %s 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'" % (ofctl, switch.name)
    )
    # eMBB e default -> fila 0
    switch.cmd(
        "%s add-flow %s 'priority=10,actions=set_queue:0,normal'" % (ofctl, switch.name)
    )

    for nome_interface in interfaces:
        configurar_qos_ovs(switch, nome_interface)


def limpar_ambiente():
    info("*** Limpando ambiente Mininet/OVS residual\n")
    os.system("mn -c 2>/dev/null")
    for nome_bridge in ["r1", "r2", "r3", "r4"]:
        os.system("ovs-vsctl --if-exists del-br %s 2>/dev/null" % nome_bridge)
    padrao_interfaces = "r[1-4]-eth|h_[a-z_]+-eth"
    try:
        saida = subprocess.check_output("ip -o link show | awk -F': ' '{print $2}' | grep -E '^(%s)'" % padrao_interfaces,
                                        shell=True, text=True)
        for interface in saida.splitlines():
            interface = interface.strip()
            if interface:
                os.system("ip link del %s 2>/dev/null" % interface)
    except subprocess.CalledProcessError:
        pass


def criar_topologia():
    limpar_ambiente()
    rede = Mininet(link=TCLink, switch=OVSSwitch)

    info("*** Criando hosts\n")
    # Unico dominio L2 /16; hosts se comunicam diretamente via L2
    host_urllc_a = rede.addHost("h_urllc_a", ip="10.0.1.1/16", mac="00:00:00:00:01:01")
    host_embb_a  = rede.addHost("h_embb_a",  ip="10.0.2.1/16", mac="00:00:00:00:02:01")
    host_urllc_b = rede.addHost("h_urllc_b", ip="10.0.3.2/16", mac="00:00:00:00:03:02")
    host_embb_b  = rede.addHost("h_embb_b",  ip="10.0.4.2/16", mac="00:00:00:00:04:02")

    info("*** Criando switches OVS\n")
    r1 = rede.addSwitch("r1", cls=OVSSwitch, protocols="OpenFlow13")
    r2 = rede.addSwitch("r2", cls=OVSSwitch, protocols="OpenFlow13")
    r3 = rede.addSwitch("r3", cls=OVSSwitch, protocols="OpenFlow13")
    r4 = rede.addSwitch("r4", cls=OVSSwitch, protocols="OpenFlow13")

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
    info("*** Testando conectividade uRLLC\n")
    resultado = rede.getNodeByName("h_urllc_a").cmd("ping -c 4 -4 10.0.3.2")
    info(resultado)


if __name__ == "__main__":
    setLogLevel("info")
    rede = criar_topologia()
    testar_conectividade(rede)

    info("*** Abrindo interface de linha de comando\n")
    CLI(rede)

    info("*** Parando rede\n")
    rede.stop()
