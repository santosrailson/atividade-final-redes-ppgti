#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time


def executar_teste_latencia():
    rede = Mininet(controller=OVSController, link=TCLink)

    controlador = rede.addController("c0")
    host_a = rede.addHost("host_a", ip="10.0.0.1/24")
    host_b = rede.addHost("host_b", ip="10.0.0.2/24")
    switch = rede.addSwitch("s1")

    rede.addLink(host_a, switch)
    rede.addLink(host_b, switch)

    rede.start()

    info("*** Iniciando servidor TCP na porta 8000 do host_b\n")
    comando_servidor = """python3 - > /tmp/servidor.log 2>&1 <<'PY' &
import socket

servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.bind(('0.0.0.0', 8000))
servidor.listen(1)

while True:
    conexao, endereco = servidor.accept()
    dados = conexao.recv(1024)
    if dados:
        conexao.sendall(dados)
    conexao.close()
PY"""
    host_b.cmd(comando_servidor)

    info("*** Aguardando servidor iniciar\n")
    time.sleep(1)

    info("*** Medindo latencia com Scapy (TCP SYN)\n")
    comando_cliente = """/root/atividade-final-redes-ppgti/.venv/bin/python3 - <<'PY'
from scapy.all import IP, TCP, sr1, conf
import time

conf.verb = 0
inicio = time.time()
pacote = IP(dst='10.0.0.2') / TCP(dport=8000, flags='S')
resposta = sr1(pacote, timeout=2)
fim = time.time()

if resposta is not None:
    latencia_ms = (fim - inicio) * 1000
    print('Latencia TCP (SYN-RTT): %.3f ms' % latencia_ms)
else:
    print('Nenhuma resposta recebida')
PY"""
    resultado = host_a.cmd(comando_cliente)
    info(resultado)

    info("*** Teste concluido\n")
    rede.stop()


if __name__ == "__main__":
    setLogLevel("info")
    executar_teste_latencia()
