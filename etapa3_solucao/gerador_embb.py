#!/usr/bin/env python3

import subprocess
import sys
import time


def iniciar_servidor(porta=5001):
    print("Iniciando servidor iperf na porta %d" % porta)
    processo = subprocess.Popen(
        ["iperf", "-s", "-p", str(porta)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return processo


def executar_cliente(endereco_destino, porta=5001, duracao_segundos=30, taxa_bits="10M", protocolo="udp"):
    print("Iniciando cliente iperf para %s:%d" % (endereco_destino, porta))

    comando = ["iperf", "-c", endereco_destino, "-p", str(porta), "-t", str(duracao_segundos), "-b", taxa_bits]
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
        servidor = iniciar_servidor()
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
