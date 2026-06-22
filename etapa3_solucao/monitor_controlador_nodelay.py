#!/usr/bin/env python3

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


def configurar_socket_nodelay(conexao):
    conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except (AttributeError, OSError):
        pass


def processar_conexao(conexao, endereco, estado_controle, latencias):
    conexao.settimeout(2.0)
    configurar_socket_nodelay(conexao)
    try:
        while True:
            try:
                conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            except (AttributeError, OSError):
                pass

            dados = conexao.recv(1024)
            if len(dados) < 8:
                break

            timestamp_envio = struct.unpack("!d", dados[:8])[0]
            timestamp_recebimento = time.time()
            latencia_ms = (timestamp_recebimento - timestamp_envio) * 1000
            latencias.append(latencia_ms)

            conexao.sendall(dados[:8])

            print("Latencia medida: %.3f ms (de %s)" % (latencia_ms, endereco[0]))
            avaliar_latencia(latencia_ms, estado_controle)
    except socket.timeout:
        pass
    except Exception as erro:
        print("Erro na conexao: %s" % erro)


def iniciar_servidor(endereco="0.0.0.0", porta=5000, duracao_segundos=60):
    print("Iniciando monitor/controlador uRLLC (nodelay) em %s:%d" % (endereco, porta))

    if os.path.exists(ARQUIVO_SINAL):
        os.remove(ARQUIVO_SINAL)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((endereco, porta))
    servidor.listen(5)
    servidor.settimeout(1.0)

    estado_controle = {"ativo": False, "violacoes_consecutivas": 0, "normais_consecutivas": 0}
    latencias = []
    tempo_inicio = time.time()

    while time.time() - tempo_inicio < duracao_segundos:
        try:
            conexao, endereco_cliente = servidor.accept()
        except socket.timeout:
            continue

        processar_conexao(conexao, endereco_cliente, estado_controle, latencias)
        conexao.close()

    servidor.close()

    with open("/tmp/latencias_receptor.csv", "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Monitor finalizado. %d medicoes salvas em /tmp/latencias_receptor.csv" % len(latencias))


if __name__ == "__main__":
    try:
        endereco = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
        porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        duracao = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
        iniciar_servidor(endereco, porta, duracao)
    except Exception as erro:
        with open("/tmp/monitor_erro.log", "w") as arquivo:
            arquivo.write(str(erro) + "\n")
            import traceback
            arquivo.write(traceback.format_exc())
        raise
