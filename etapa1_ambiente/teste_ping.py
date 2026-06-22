#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.link import TCLink
from mininet.log import setLogLevel, info


def executar_teste_ping():
    rede = Mininet(controller=OVSController, link=TCLink)

    controlador = rede.addController("c0")
    host_a = rede.addHost("host_a", ip="10.0.0.1/24")
    host_b = rede.addHost("host_b", ip="10.0.0.2/24")
    switch = rede.addSwitch("s1")

    rede.addLink(host_a, switch)
    rede.addLink(host_b, switch)

    rede.start()

    info("*** Executando ping de host_a para host_b\n")
    resultado = host_a.cmd("ping -c 4 10.0.0.2")
    info(resultado)

    info("*** Teste concluido\n")
    rede.stop()


if __name__ == "__main__":
    setLogLevel("info")
    executar_teste_ping()
