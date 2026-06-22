#!/usr/bin/env python3

import socket
import struct
import time
import sys


def criar_conexao(endereco_destino, porta_destino):
    conexao = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conexao.settimeout(5.0)
    conexao.connect((endereco_destino, porta_destino))
    return conexao


def enviar_pacote_urllc(conexao):
    timestamp_envio = time.time()
    payload = struct.pack("!d", timestamp_envio)
    conexao.sendall(payload)

    dados = conexao.recv(1024)
    if len(dados) < 8:
        return None

    timestamp_chegada = time.time()
    latencia_ms = (timestamp_chegada - timestamp_envio) * 1000
    return latencia_ms


def executar_gerador(endereco_destino, porta_destino, intervalo_segundos, duracao_segundos):
    print("Iniciando gerador uRLLC para %s:%d" % (endereco_destino, porta_destino))
    latencias = []
    conexao = None

    tempo_inicio = time.time()
    while time.time() - tempo_inicio < duracao_segundos:
        try:
            if conexao is None:
                conexao = criar_conexao(endereco_destino, porta_destino)

            latencia = enviar_pacote_urllc(conexao)
            if latencia is not None:
                latencias.append(latencia)
                print("Latencia uRLLC: %.3f ms" % latencia)
            else:
                print("Falha ao medir latencia, reconectando")
                conexao.close()
                conexao = None
        except (socket.timeout, socket.error, BrokenPipeError) as erro:
            print("Erro de conexao: %s, reconectando" % erro)
            if conexao:
                try:
                    conexao.close()
                except Exception:
                    pass
            conexao = None

        time.sleep(intervalo_segundos)

    if conexao:
        conexao.close()

    with open("/tmp/latencias_urllc.csv", "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Gerador uRLLC finalizado. %d medicoes salvas em /tmp/latencias_urllc.csv" % len(latencias))


if __name__ == "__main__":
    endereco = sys.argv[1] if len(sys.argv) > 1 else "10.0.3.2"
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    intervalo = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    duracao = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
    executar_gerador(endereco, porta, intervalo, duracao)
