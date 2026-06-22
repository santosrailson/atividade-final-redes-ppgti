#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def criar_topologia():
    rede = Mininet(controller=OVSController, link=TCLink)

    info("*** Criando controlador\n")
    controlador = rede.addController("c0")

    info("*** Criando hosts\n")
    host_a = rede.addHost("host_a", ip="10.0.0.1/24")
    host_b = rede.addHost("host_b", ip="10.0.0.2/24")

    info("*** Criando switch\n")
    switch = rede.addSwitch("s1")

    info("*** Criando links\n")
    rede.addLink(host_a, switch, bw=100)
    rede.addLink(host_b, switch, bw=100)

    info("*** Iniciando rede\n")
    rede.start()

    info("*** Testando conectividade\n")
    rede.pingAll()

    info("*** Abrindo interface de linha de comando\n")
    CLI(rede)

    info("*** Parando rede\n")
    rede.stop()


if __name__ == "__main__":
    setLogLevel("info")
    criar_topologia()
