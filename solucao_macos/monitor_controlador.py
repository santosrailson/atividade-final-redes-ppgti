#!/usr/bin/env python3
"""
Monitor + controlador closed loop do tráfego uRLLC (Scapy/TCP).

Este processo roda no host de destino (h_urllc_b) e cumpre dois papéis:

1. Monitor: recebe cada pacote uRLLC, calcula a latência one-way
   (chegada - timestamp de envio embutido no payload) e devolve um eco
   ao gerador. Assume relógios sincronizados entre os hosts (dentro do
   mesmo container/VM Mininet, o relógio de sistema é compartilhado
   por todos os namespaces, então essa suposição é válida aqui).

2. Controlador: aplica uma lógica de histerese sobre a latência
   medida. Se a latência ultrapassa o limiar (5 ms) por
   `JANELA_VIOLACOES` medições seguidas, escreve um sinal "ativar" em
   um arquivo compartilhado. O processo orquestrador (experimento.py)
   lê esse arquivo e instala, via OpenFlow, uma regra que descarta o
   tráfego eMBB nos switches OVS -- protegendo o uRLLC. Quando a
   latência volta ao normal por `AMOSTRAS_PARA_NORMALIZAR` medições
   seguidas, o sinal "desativar" libera o eMBB de novo.

A comunicação monitor -> orquestrador via arquivo (em vez de, por
exemplo, uma fila em memória) é proposital: monitor e orquestrador
são processos/hosts Mininet diferentes, então um arquivo em disco
compartilhado é a forma mais simples de sinalizar entre eles.
"""

import os
import socket
import struct
import sys
import time

from scapy.all import conf, IP, TCP, Raw, StreamSocket

conf.verb = 0

LIMIAR_LATENCIA_MS = 5.0      # requisito do projeto: uRLLC <= 5 ms fim-a-fim
JANELA_VIOLACOES = 2          # violações consecutivas para ativar o controle
AMOSTRAS_PARA_NORMALIZAR = 3  # medições normais consecutivas para desativar

DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_PROJETO, "resultados")
os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)

ARQUIVO_SINAL = os.path.join(DIRETORIO_RESULTADOS, "sinal_controle_qos")
ARQUIVO_LATENCIAS = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc.csv")
ARQUIVO_ERRO = os.path.join(DIRETORIO_RESULTADOS, "monitor_erro.log")


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


def enviar_sinal(acao):
    """Escreve o comando de controle (ativar/desativar) no arquivo que
    o orquestrador (experimento.py) fica observando."""
    with open(ARQUIVO_SINAL, "w") as arquivo:
        arquivo.write(acao + "\n")
    print("Sinal enviado: %s" % acao, flush=True)


def avaliar_latencia(latencia_ms, estado_controle):
    """Máquina de estados simples com histerese para evitar oscilação
    (ligar/desligar o controle a cada medição isolada acima/abaixo do
    limiar)."""
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


def processar_conexao(soquete_cliente, endereco, estado_controle, latencias):
    soquete_cliente.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 7)
    soquete_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        soquete_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except (AttributeError, OSError):
        pass
    conexao = StreamSocket(soquete_cliente, IP)
    resposta_base = IP(dst=endereco[0], tos=0xB8) / TCP(dport=5000) / Raw(load=b"\x00" * 8)

    try:
        while True:
            try:
                pacote = conexao.recv()
            except socket.timeout:
                break
            except Exception:
                break

            if pacote is None or Raw not in pacote:
                continue

            dados = bytes(pacote[Raw].load)
            if len(dados) < 8:
                continue

            timestamp_envio = struct.unpack("!d", dados[:8])[0]
            timestamp_recebimento = time.time()
            latencia_ms = (timestamp_recebimento - timestamp_envio) * 1000
            latencias.append(latencia_ms)

            resposta_base[Raw].load = dados[:8]
            conexao.send(resposta_base)

            print("Latência medida: %.3f ms (de %s)" % (latencia_ms, endereco[0]), flush=True)
            avaliar_latencia(latencia_ms, estado_controle)
    except Exception as erro:
        print("Erro na conexão: %s" % erro, flush=True)
    finally:
        try:
            conexao.close()
        except Exception:
            pass


def iniciar_servidor(endereco="0.0.0.0", porta=5000, duracao_segundos=60):
    configurar_prioridade()
    print("Iniciando monitor/controlador uRLLC em %s:%d" % (endereco, porta), flush=True)

    if os.path.exists(ARQUIVO_SINAL):
        os.remove(ARQUIVO_SINAL)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 7)
    servidor.bind((endereco, porta))
    servidor.listen(5)
    servidor.settimeout(1.0)  # permite checar o tempo total mesmo sem clientes

    estado_controle = {"ativo": False, "violacoes_consecutivas": 0, "normais_consecutivas": 0}
    latencias = []
    tempo_inicio = time.time()

    while time.time() - tempo_inicio < duracao_segundos:
        try:
            soquete_cliente, endereco_cliente = servidor.accept()
        except socket.timeout:
            continue

        soquete_cliente.settimeout(2.0)
        processar_conexao(soquete_cliente, endereco_cliente, estado_controle, latencias)

    servidor.close()

    # As latências one-way salvas aqui são a fonte principal usada por
    # analisar_resultados.py para gerar as estatísticas e os gráficos.
    with open(ARQUIVO_LATENCIAS, "w") as arquivo:
        arquivo.write("latencia_ms\n")
        for valor in latencias:
            arquivo.write("%.3f\n" % valor)

    print("Monitor finalizado. %d medições salvas em %s" % (len(latencias), ARQUIVO_LATENCIAS), flush=True)


if __name__ == "__main__":
    try:
        endereco = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
        porta = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        duracao = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
        iniciar_servidor(endereco, porta, duracao)
    except Exception as erro:
        with open(ARQUIVO_ERRO, "w") as arquivo:
            arquivo.write(str(erro) + "\n")
            import traceback
            arquivo.write(traceback.format_exc())
        raise
