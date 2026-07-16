#!/usr/bin/env python3
"""
Monitor + controlador closed loop do tráfego uRLLC (Scapy/TCP).

Este processo roda no host da Central de Monitoramento do campus
(h_central_urllc) e cumpre dois papéis:

1. Monitor: recebe cada pacote uRLLC -- alertas de sensores de
   incêndio/fumaça vindos de vários prédios do campus, cada um em sua
   própria conexão TCP concorrente --, calcula a latência one-way
   (chegada - timestamp de envio embutido no payload) e devolve um eco
   ao gerador. Assume relógios sincronizados entre os hosts (dentro do
   mesmo container/VM Mininet, o relógio de sistema é compartilhado
   por todos os namespaces, então essa suposição é válida aqui).

2. Controlador: aplica uma lógica de histerese sobre a latência
   medida (agregada entre todos os sites). Se a latência ultrapassa o
   limiar (5 ms) por `JANELA_VIOLACOES` medições seguidas, escreve um
   sinal "ativar" em um arquivo compartilhado. O processo orquestrador
   (experimento.py) lê esse arquivo e instala, via OpenFlow, uma regra
   que reduz a taxa das filas eMBB nos switches OVS -- protegendo o
   uRLLC sem interromper o outro serviço. Quando a latência volta ao normal por
   `AMOSTRAS_PARA_NORMALIZAR` medições seguidas, o sinal "desativar"
   restaura a taxa normal do eMBB.

A comunicação monitor -> orquestrador via arquivo (em vez de, por
exemplo, uma fila em memória) é proposital: monitor e orquestrador
são processos/hosts Mininet diferentes, então um arquivo em disco
compartilhado é a forma mais simples de sinalizar entre eles.

Como os sensores de vários prédios enviam alertas simultaneamente, o
servidor aceita conexões concorrentes: cada conexão é atendida em uma
thread própria, e o estado do controlador (contadores de violação,
lista de latências) é compartilhado entre elas com um lock.
"""

import os
import socket
import sys
import threading
import time

from scapy.all import conf, Raw, StreamSocket

from protocolo_urllc import TAMANHO_MENSAGEM, codificar_mensagem, extrair_mensagens

conf.verb = 0

LIMIAR_LATENCIA_MS = 5.0      # requisito do projeto: uRLLC <= 5 ms fim-a-fim
JANELA_VIOLACOES = 2          # violações consecutivas para ativar o controle
AMOSTRAS_PARA_NORMALIZAR = 3  # medições normais consecutivas para desativar

# Prefixo IP (/24) -> nome do site do campus, só para identificar a
# origem do alerta nos logs em tempo real (não afeta a medição).
MAPA_SITES = {
    "10.0.11.": "Biblioteca",
    "10.0.21.": "Laboratorios",
    "10.0.31.": "Reitoria",
}


def nome_do_site(ip):
    for prefixo, nome in MAPA_SITES.items():
        if ip.startswith(prefixo):
            return nome
    return ip

DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RESULTADOS = os.environ.get("RESULTADOS_DIR", os.path.join(DIRETORIO_PROJETO, "resultados"))
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
    limiar). Chamada só sob `estado_controle["lock"]`, já que os
    sensores dos vários prédios do campus reportam concorrentemente e
    esse estado é compartilhado entre as threads."""
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
    """Atende, em sua própria thread, os alertas de um sensor. Roda em
    paralelo com as threads dos outros prédios do campus, todas
    compartilhando `estado_controle` e `latencias` sob o mesmo lock."""
    soquete_cliente.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 7)
    soquete_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        soquete_cliente.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    except (AttributeError, OSError):
        pass
    conexao = StreamSocket(soquete_cliente, Raw)
    site = nome_do_site(endereco[0])
    buffer = b""

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

            buffer += bytes(pacote[Raw].load)
            mensagens, buffer = extrair_mensagens(buffer)
            for sequencia, timestamp_envio in mensagens:
                timestamp_recebimento = time.time()
                latencia_ms = max(0.0, (timestamp_recebimento - timestamp_envio) * 1000)
                conexao.send(Raw(load=codificar_mensagem(sequencia, timestamp_envio)))

                print("Latência medida: %.3f ms (de %s - %s, seq=%d)" %
                      (latencia_ms, endereco[0], site, sequencia), flush=True)

                with estado_controle["lock"]:
                    latencias.append((timestamp_recebimento, endereco[0], site, sequencia, latencia_ms))
                    with open(ARQUIVO_LATENCIAS, "a") as arquivo:
                        arquivo.write("%.6f,%s,%s,%d,%.3f\n" %
                                      (timestamp_recebimento, endereco[0], site, sequencia, latencia_ms))
                        arquivo.flush()
                    avaliar_latencia(latencia_ms, estado_controle)
    except Exception as erro:
        print("Erro na conexão (%s): %s" % (site, erro), flush=True)
    finally:
        try:
            conexao.close()
        except Exception:
            pass


def iniciar_servidor(endereco="0.0.0.0", porta=5000, duracao_segundos=60):
    configurar_prioridade()
    print("Iniciando monitor/controlador uRLLC em %s:%d (Central de Monitoramento do campus)" % (endereco, porta), flush=True)

    if os.path.exists(ARQUIVO_SINAL):
        os.remove(ARQUIVO_SINAL)
    # Escrita incremental: uma interrupção não elimina as evidências já
    # coletadas e o orquestrador pode validar a execução sem esperar o timeout.
    with open(ARQUIVO_LATENCIAS, "w") as arquivo:
        arquivo.write("timestamp_recebimento,ip_origem,site,sequencia,latencia_ms\n")

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 7)
    servidor.bind((endereco, porta))
    servidor.listen(len(MAPA_SITES) + 1)
    servidor.settimeout(1.0)  # permite checar o tempo total mesmo sem clientes

    estado_controle = {
        "ativo": False,
        "violacoes_consecutivas": 0,
        "normais_consecutivas": 0,
        "lock": threading.Lock(),
    }
    latencias = []
    threads_conexoes = []
    tempo_inicio = time.time()

    while time.time() - tempo_inicio < duracao_segundos:
        try:
            soquete_cliente, endereco_cliente = servidor.accept()
        except socket.timeout:
            continue

        soquete_cliente.settimeout(2.0)
        # Cada prédio do campus mantém sua própria conexão TCP com a
        # central; atender cada uma em uma thread permite medir os 3
        # sites em paralelo, em vez de travar o accept() de novos
        # sites enquanto um sensor já conectado continua enviando.
        thread = threading.Thread(
            target=processar_conexao,
            args=(soquete_cliente, endereco_cliente, estado_controle, latencias),
            daemon=True,
        )
        thread.start()
        threads_conexoes.append(thread)

    for thread in threads_conexoes:
        thread.join(timeout=3.0)

    servidor.close()

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
