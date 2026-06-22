#!/usr/bin/env python3
"""
Receptor uRLLC via UDP.

Recebe pacotes UDP contendo um timestamp de envio no payload, calcula a
latencia fim-a-fim e envia sinais de controle quando a latencia ultrapassa o
limiar configurado.

Uso:
    python3 receptor_urllc_udp.py <endereco_local> <porta> <duracao_s>
"""

import os
import socket
import struct
import sys
import time

LIMIAR_LATENCIA_MS = 5.0
JANELA_VIOLACOES = 2
AMOSTRAS_PARA_NORMALIZAR = 3
ARQUIVO_SINAL = "/tmp/sinal_controle_qos"


def enviar_sinal(acao):
    with open(ARQUIVO_SINAL, "w") as arquivo:
        arquivo.write(acao + "\n")
    print("Sinal enviado: %s" % acao)


def avaliar_latencia(latencia_ms, estado_controle):
    if latencia_ms > LIMIAR_LATENCIA_MS:
        estado_controle["violacoes_consecutivas"] += 1
        estado_controle["normais_consecutivas"] = 0
        if estado_controle["violacoes_consecutivas"] >= JANELA_VIOLACOES and not estado_controle["ativo"]:
            enviar_sinal("ativar")
            estado_controle["ativo"] = True
    else:
        estado_controle["normais_consecutivas"] += 1
        estado_controle["violacoes_consecutivas"] = 0
        if estado_controle["normais_consecutivas"] >= AMOSTRAS_PARA_NORMALIZAR and estado_controle["ativo"]:
            enviar_sinal("desativar")
            estado_controle["ativo"] = False


def main():
    endereco = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    duracao = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0

    if os.path.exists(ARQUIVO_SINAL):
        os.remove(ARQUIVO_SINAL)

    soquete = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soquete.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    soquete.bind((endereco, porta))
    soquete.settimeout(2.0)

    print("Receptor uRLLC UDP iniciado em %s:%d" % (endereco, porta))

    estado_controle = {"ativo": False, "violacoes_consecutivas": 0, "normais_consecutivas": 0}
    latencias = []
    tempo_inicio = time.time()

    while time.time() - tempo_inicio < duracao:
        try:
            dados, endereco_cliente = soquete.recvfrom(1024)
        except socket.timeout:
            continue

        if len(dados) < 8:
            continue

        timestamp_envio = struct.unpack("!d", dados[:8])[0]
        timestamp_recebimento = time.time()
        latencia_ms = (timestamp_recebimento - timestamp_envio) * 1000
        latencias.append(latencia_ms)

        print("Latencia medida: %.3f ms (de %s)" % (latencia_ms, endereco_cliente[0]))
        avaliar_latencia(latencia_ms, estado_controle)

    soquete.close()

    with open("/tmp/latencias_receptor.csv", "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Receptor finalizado. %d medicoes salvas em /tmp/latencias_receptor.csv" % len(latencias))


if __name__ == "__main__":
    main()
