#!/usr/bin/env python3
"""
Gerador de tráfego eMBB (enhanced Mobile Broadband) usando iperf3.

O eMBB representa o tráfego "concorrente" de alto volume (streaming,
grandes transferências) que disputa banda com o uRLLC na mesma rede
de transporte. Usamos iperf3 (em vez do iperf 2.x original) porque é
o pacote disponível e mantido no apt do Ubuntu 22.04 usado na imagem
Docker deste projeto -- a interface de linha de comando (-s/-c/-u/-b)
é equivalente para o que precisamos aqui.
"""

import subprocess
import sys
import time


def iniciar_servidor(porta=5001):
    print("Iniciando servidor iperf3 na porta %d" % porta)
    processo = subprocess.Popen(
        ["iperf3", "-s", "-p", str(porta)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return processo


def executar_cliente(endereco_destino, porta=5001, duracao_segundos=30, taxa_bits="10M", protocolo="udp"):
    print("Iniciando cliente iperf3 para %s:%d (%s, %s)" % (endereco_destino, porta, taxa_bits, protocolo.upper()))

    comando = ["iperf3", "-c", endereco_destino, "-p", str(porta), "-t", str(duracao_segundos), "-b", taxa_bits]
    if protocolo == "udp":
        comando.append("-u")

    processo = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    saida, erro = processo.communicate()
    print(saida)
    if erro:
        print(erro, file=sys.stderr)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "cliente"

    if modo == "servidor":
        porta_servidor = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
        servidor = iniciar_servidor(porta_servidor)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            servidor.terminate()
            servidor.wait()
    else:
        endereco = sys.argv[2] if len(sys.argv) > 2 else "10.0.4.2"
        porta = int(sys.argv[3]) if len(sys.argv) > 3 else 5001
        duracao = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        taxa = sys.argv[5] if len(sys.argv) > 5 else "10M"
        protocolo = sys.argv[6] if len(sys.argv) > 6 else "udp"
        executar_cliente(endereco, porta, duracao, taxa, protocolo)
