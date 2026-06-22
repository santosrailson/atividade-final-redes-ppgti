#!/usr/bin/env python3
"""
Gerador uRLLC otimizado com Scapy/TCP (StreamSocket sobre socket TCP puro).

- Usa StreamSocket do Scapy, que envolve um socket TCP real.
- Constroi pacote Scapy IP/TCP/Raw e envia via StreamSocket.
- Aplica TCP_NODELAY, TCP_QUICKACK, SO_PRIORITY e ToS EF.
- Configura prioridade de processo.
"""

import os
import socket
import struct
import sys
import time

from scapy.all import conf, IP, TCP, Raw, StreamSocket

conf.verb = 0

DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_PROJETO, "docs", "resultados")
if not os.path.exists(DIRETORIO_RESULTADOS):
    os.makedirs(DIRETORIO_RESULTADOS)

ARQUIVO_LATENCIAS_RTT = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc_rtt.csv")


def configurar_prioridade():
    try:
        os.nice(-20)
    except Exception:
        pass
    try:
        param = os.sched_param(os.sched_get_priority_max(os.SCHED_FIFO))
        os.sched_setscheduler(0, os.SCHED_FIFO, param)
    except Exception:
        pass


def criar_conexao_scapy(endereco_destino, porta_destino):
    soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soquete.settimeout(5.0)
    soquete.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 7)
    soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except (AttributeError, OSError):
        pass
    soquete.connect((endereco_destino, porta_destino))
    return StreamSocket(soquete, Raw)


def enviar_pacote_urllc(conexao, pacote_base):
    timestamp_envio = time.time()
    payload = struct.pack("!d", timestamp_envio)

    pacote_base[Raw].load = payload
    conexao.send(pacote_base)

    resposta = conexao.recv()
    if resposta is None or Raw not in resposta:
        return None

    timestamp_chegada = time.time()
    latencia_ms = (timestamp_chegada - timestamp_envio) * 1000
    return latencia_ms


def executar_gerador(endereco_destino, porta_destino, intervalo_segundos, duracao_segundos):
    configurar_prioridade()
    print("Iniciando gerador uRLLC com Scapy/TCP (StreamSocket) para %s:%d" % (endereco_destino, porta_destino), flush=True)
    latencias = []
    conexao = None
    pacote_base = IP(dst=endereco_destino, tos=0xB8) / TCP(dport=porta_destino) / Raw(load=b"\x00" * 8)

    tempo_inicio = time.time()
    while time.time() - tempo_inicio < duracao_segundos:
        try:
            if conexao is None:
                conexao = criar_conexao_scapy(endereco_destino, porta_destino)

            latencia = enviar_pacote_urllc(conexao, pacote_base)
            if latencia is not None:
                latencias.append(latencia)
                print("Latencia uRLLC (Scapy StreamSocket): %.3f ms" % latencia, flush=True)
            else:
                print("Falha ao medir latencia, reconectando", flush=True)
                conexao.close()
                conexao = None
        except (socket.timeout, socket.error, BrokenPipeError, OSError) as erro:
            print("Erro de conexao: %s, reconectando" % erro, flush=True)
            if conexao:
                try:
                    conexao.close()
                except Exception:
                    pass
            conexao = None

        time.sleep(intervalo_segundos)

    if conexao:
        try:
            conexao.close()
        except Exception:
            pass

    with open(ARQUIVO_LATENCIAS_RTT, "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Gerador uRLLC (Scapy StreamSocket) finalizado. %d medicoes salvas em %s" % (len(latencias), ARQUIVO_LATENCIAS_RTT), flush=True)


if __name__ == "__main__":
    endereco = sys.argv[1] if len(sys.argv) > 1 else "10.0.3.2"
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    intervalo = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    duracao = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
    executar_gerador(endereco, porta, intervalo, duracao)
