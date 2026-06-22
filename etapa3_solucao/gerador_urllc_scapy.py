#!/usr/bin/env python3

import socket
import struct
import time
import sys

from scapy.all import IP, TCP, Raw, StreamSocket


def criar_conexao_scapy(endereco_destino, porta_destino):
    soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soquete.settimeout(5.0)
    soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except (AttributeError, OSError):
        pass
    soquete.connect((endereco_destino, porta_destino))
    return StreamSocket(soquete, Raw)


def enviar_pacote_urllc(conexao, endereco_destino, porta_destino):
    timestamp_envio = time.time()
    payload = struct.pack("!d", timestamp_envio)

    pacote = IP(dst=endereco_destino) / TCP(dport=porta_destino) / Raw(load=payload)
    conexao.send(pacote)

    resposta = conexao.recv()
    if resposta is None or Raw not in resposta:
        return None

    dados_resposta = bytes(resposta[Raw].load)
    if len(dados_resposta) < 8:
        return None

    timestamp_chegada = time.time()
    latencia_ms = (timestamp_chegada - timestamp_envio) * 1000
    return latencia_ms


def executar_gerador(endereco_destino, porta_destino, intervalo_segundos, duracao_segundos):
    print("Iniciando gerador uRLLC com Scapy/TCP para %s:%d" % (endereco_destino, porta_destino))
    latencias = []
    conexao = None

    tempo_inicio = time.time()
    while time.time() - tempo_inicio < duracao_segundos:
        try:
            if conexao is None:
                conexao = criar_conexao_scapy(endereco_destino, porta_destino)

            latencia = enviar_pacote_urllc(conexao, endereco_destino, porta_destino)
            if latencia is not None:
                latencias.append(latencia)
                print("Latencia uRLLC (Scapy): %.3f ms" % latencia)
            else:
                print("Falha ao medir latencia, reconectando")
                conexao.close()
                conexao = None
        except (socket.timeout, socket.error, BrokenPipeError, OSError) as erro:
            print("Erro de conexao: %s, reconectando" % erro)
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

    with open("/tmp/latencias_urllc.csv", "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Gerador uRLLC (Scapy) finalizado. %d medicoes salvas em /tmp/latencias_urllc.csv" % len(latencias))


if __name__ == "__main__":
    endereco = sys.argv[1] if len(sys.argv) > 1 else "10.0.3.2"
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    intervalo = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    duracao = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
    executar_gerador(endereco, porta, intervalo, duracao)
