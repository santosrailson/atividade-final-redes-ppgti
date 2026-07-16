#!/usr/bin/env python3
"""
Orquestrador do experimento closed loop uRLLC x eMBB sobre 4 switches OVS.

Cenário: rede de monitoramento de segurança/incêndio de um campus
universitário. Três prédios (Biblioteca, Laboratórios, Reitoria) enviam
simultaneamente, cada um pela sua própria conexão:

- uRLLC: alertas de sensores de incêndio/fumaça (TCP porta 5000) para
  a Central de Monitoramento (`h_central_urllc`).
- eMBB: streaming das câmeras de vigilância (iperf3, uma porta por
  prédio) para a Central de Vídeo (`h_central_video`).

Fluxo de um experimento:

1. Sobe a topologia (topologia.py) com os 3 sites + a central.
2. Configura ou omite a classificação QoS estática, conforme o grupo.
3. Inicia o monitor/controlador na Central (monitor_controlador.py),
   que atende os 3 sensores concorrentemente.
4. Inicia um servidor iperf3 por prédio na Central de Vídeo e o
   respectivo cliente na câmera de cada prédio (gerador_embb.py), a
   menos que o experimento seja "uRLLC isolado" (--sem-embb).
5. Inicia o gerador de tráfego uRLLC em cada sensor (gerador_urllc.py).
6. Fica observando o arquivo de sinal escrito pelo monitor e, quando
   necessário, reduz/restaura a taxa das filas eMBB nos quatro OVS --
   fechando o laço de controle sem interromper completamente o serviço
   (closed loop).
7. Ao final, chama analisar_resultados.py para gerar estatísticas e
   os gráficos usados no artigo (latências agregadas dos 3 sites).

Diferença em relação à versão Linux original: nenhum caminho fixo de
usuário/máquina (ex.: /root/...). Tudo é resolvido a partir da pasta
onde este arquivo está (`DIRETORIO_PROJETO`) e do interpretador Python
em uso (`sys.executable`), então o mesmo código funciona tanto dentro
do container Docker quanto fora dele.
"""

import argparse
import os
import subprocess
import sys
import time

DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIRETORIO_PROJETO)

from topologia import (
    criar_topologia, SITES, HOST_CENTRAL_URLLC, HOST_CENTRAL_VIDEO,
    TAXA_EMBB_NORMAL_BPS, TAXA_EMBB_PROTEGIDA_BPS,
)

DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_PROJETO, "resultados")
os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)

ARQUIVO_SINAL = os.path.join(DIRETORIO_RESULTADOS, "sinal_controle_qos")
ARQUIVO_EVENTOS = os.path.join(DIRETORIO_RESULTADOS, "eventos_controle.txt")
ARQUIVO_LATENCIAS = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc.csv")

IP_CENTRAL_URLLC = HOST_CENTRAL_URLLC[1].split("/")[0]
IP_CENTRAL_VIDEO = HOST_CENTRAL_VIDEO[1].split("/")[0]
PORTA_URLLC = 5000

# Uma porta eMBB dedicada por prédio (um servidor/cliente iperf3 por
# porta), já que um mesmo servidor iperf3 não atende dois streams UDP
# simultâneos na mesma porta -- é assim que os 3 prédios conseguem
# transmitir vídeo para a central ao mesmo tempo.
PORTAS_EMBB = {site["nome"]: 5001 + indice for indice, site in enumerate(SITES)}

# Usa sempre o mesmo interpretador Python que executou este script
# (o do venv/imagem Docker), em vez de um caminho fixo.
CAMINHO_PYTHON = sys.executable


def registrar_evento(mensagem):
    with open(ARQUIVO_EVENTOS, "a") as arquivo:
        arquivo.write("%.3f\t%s\n" % (time.time(), mensagem))


def aplicar_controle_qos(rede, ativar):
    """Reduz ou restaura a taxa máxima das filas eMBB nos quatro OVS.

    A proteção mantém o serviço eMBB ativo em banda reduzida, em vez de
    descartá-lo completamente, e pode ser revertida pela histerese.
    """
    acao = "ativar" if ativar else "desativar"
    print("*** Aplicando controle QoS (OpenFlow): %s ***" % acao)
    registrar_evento("controle_%s" % acao)
    taxa = TAXA_EMBB_PROTEGIDA_BPS if ativar else TAXA_EMBB_NORMAL_BPS
    for nome_switch in ["r1", "r2", "r3", "r4"]:
        switch = rede.getNodeByName(nome_switch)
        switch.cmd(
            "for q in $(ovs-vsctl --bare --columns=_uuid find Queue external_ids:classe=embb); "
            "do ovs-vsctl set Queue $q other-config:max-rate=%d; done" % taxa
        )


class LeitorIncremental:
    """Acompanha um arquivo de log que outro processo (rodando em outro
    host Mininet) vai escrevendo aos poucos, e imprime só as linhas
    novas desde a ultima leitura -- e o que da a sensacao de "tempo
    real" no terminal do orquestrador, mesmo com gerador/monitor/eMBB
    rodando como processos separados com stdout redirecionado para
    arquivo."""

    def __init__(self, caminho, prefixo):
        self.caminho = caminho
        self.prefixo = prefixo
        self.posicao = 0

    def imprimir_novas_linhas(self):
        if not os.path.exists(self.caminho):
            return
        with open(self.caminho, "r") as arquivo:
            arquivo.seek(self.posicao)
            conteudo_novo = arquivo.read()
            self.posicao = arquivo.tell()
        for linha in conteudo_novo.splitlines():
            linha = linha.strip()
            if linha:
                print("[%s] %s" % (self.prefixo, linha), flush=True)


def monitorar_sinal_e_atuar(rede, duracao_segundos, leitores, controle_habilitado):
    """Le periodicamente o arquivo de sinal escrito pelo monitor
    (monitor_controlador.py, rodando em outro host Mininet) e aplica a
    acao correspondente nos switches. Esse polling de arquivo e o que
    fecha o laco entre "monitoramento" (outro processo) e "atuacao"
    (aqui, que tem acesso aos objetos Mininet/OVS).

    No mesmo loop, tambem repassa em tempo real (a cada 0.2s) qualquer
    linha nova escrita pelos processos de monitor/gerador/eMBB, e
    imprime um marcador de progresso a cada 5s -- assim o terminal
    nunca fica mudo durante os `duracao_segundos` do experimento.
    """
    controle_ativo = False
    tempo_inicio = time.time()
    ultimo_marcador = tempo_inicio
    registrar_evento("inicio_monitoramento")
    while time.time() - tempo_inicio < duracao_segundos:
        if os.path.exists(ARQUIVO_SINAL):
            with open(ARQUIVO_SINAL, "r") as arquivo:
                sinal = arquivo.read().strip()
            os.remove(ARQUIVO_SINAL)

            if sinal == "ativar" and not controle_habilitado:
                print("*** Sinal de controle observado, mas atuação desabilitada neste cenário ***")
            elif sinal == "ativar" and not controle_ativo:
                aplicar_controle_qos(rede, True)
                controle_ativo = True
            elif sinal == "desativar" and controle_ativo:
                aplicar_controle_qos(rede, False)
                controle_ativo = False

        for leitor in leitores:
            leitor.imprimir_novas_linhas()

        agora = time.time()
        if agora - ultimo_marcador >= 5:
            print(
                "--- decorridos %d/%ds ---" % (int(agora - tempo_inicio), duracao_segundos),
                flush=True
            )
            ultimo_marcador = agora

        time.sleep(0.2)

    # Uma ultima passada garante que nenhuma linha escrita nos instantes
    # finais (apos a ultima iteracao do laco) fique de fora do terminal.
    for leitor in leitores:
        leitor.imprimir_novas_linhas()
    registrar_evento("fim_monitoramento")


def executar_experimento(duracao_segundos, taxa_embb, tipo_embb, controle, sem_embb,
                         intervalo_urllc, qos_estatico, diretorio_saida):
    global DIRETORIO_RESULTADOS, ARQUIVO_SINAL, ARQUIVO_EVENTOS, ARQUIVO_LATENCIAS
    DIRETORIO_RESULTADOS = os.path.abspath(diretorio_saida)
    os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)
    os.environ["RESULTADOS_DIR"] = DIRETORIO_RESULTADOS
    ARQUIVO_SINAL = os.path.join(DIRETORIO_RESULTADOS, "sinal_controle_qos")
    ARQUIVO_EVENTOS = os.path.join(DIRETORIO_RESULTADOS, "eventos_controle.txt")
    ARQUIVO_LATENCIAS = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc.csv")
    for arquivo in [ARQUIVO_EVENTOS, ARQUIVO_LATENCIAS, ARQUIVO_SINAL]:
        if os.path.exists(arquivo):
            os.remove(arquivo)

    rede = criar_topologia(qos_estatico=qos_estatico)

    h_central_urllc = rede.getNodeByName(HOST_CENTRAL_URLLC[0])
    h_central_video = rede.getNodeByName(HOST_CENTRAL_VIDEO[0])

    caminho_log_monitor = os.path.join(DIRETORIO_RESULTADOS, "monitor.log")
    leitores = [LeitorIncremental(caminho_log_monitor, "monitor")]

    print("*** Iniciando monitor/controlador na Central de Monitoramento (%s)" % HOST_CENTRAL_URLLC[0])
    h_central_urllc.cmd(
        "RESULTADOS_DIR=%s %s %s %s %d %d > %s 2>&1 &"
        % (DIRETORIO_RESULTADOS, CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "monitor_controlador.py"),
           IP_CENTRAL_URLLC, PORTA_URLLC, duracao_segundos + 20, caminho_log_monitor)
    )
    time.sleep(3)  # dá tempo do monitor abrir o socket de escuta antes dos geradores conectarem

    processos_cliente_iperf = []
    if not sem_embb:
        for site in SITES:
            porta_embb = PORTAS_EMBB[site["nome"]]
            print("*** Iniciando servidor iperf3 em %s (porta %d, prédio %s)"
                  % (HOST_CENTRAL_VIDEO[0], porta_embb, site["nome"]))
            h_central_video.cmd(
                "%s %s servidor %d > %s 2>&1 &"
                % (CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_embb.py"), porta_embb,
                   os.path.join(DIRETORIO_RESULTADOS, "embb_servidor_%s.log" % site["nome"]))
            )
        time.sleep(2)

        for site in SITES:
            nome_camera = site["camera"][0]
            porta_embb = PORTAS_EMBB[site["nome"]]
            h_camera = rede.getNodeByName(nome_camera)
            print("*** Iniciando câmera do prédio %s (%s -> %s:%d, %s %s)"
                  % (site["nome"], nome_camera, IP_CENTRAL_VIDEO, porta_embb, taxa_embb, tipo_embb.upper()))
            arquivo_log = os.path.join(DIRETORIO_RESULTADOS, "embb_%s.log" % site["nome"])
            processo = h_camera.popen(
                [CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_embb.py"),
                 "cliente", IP_CENTRAL_VIDEO, str(porta_embb), str(duracao_segundos), taxa_embb, tipo_embb],
                stdout=open(arquivo_log, "w"),
                stderr=subprocess.STDOUT
            )
            leitores.append(LeitorIncremental(arquivo_log, "embb-%s" % site["nome"]))
            processos_cliente_iperf.append(processo)
        time.sleep(3)
    else:
        print("*** Experimento SEM eMBB (uRLLC isolado, sem câmeras)")
        registrar_evento("sem_embb")

    processos_gerador_urllc = []
    for site in SITES:
        nome_sensor = site["sensor"][0]
        h_sensor = rede.getNodeByName(nome_sensor)
        print("*** Iniciando sensor de incêndio do prédio %s (%s, intervalo %.1fs)"
              % (site["nome"], nome_sensor, intervalo_urllc))
        arquivo_log = os.path.join(DIRETORIO_RESULTADOS, "urllc_%s.log" % site["nome"])
        processo = h_sensor.popen(
            [CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_urllc.py"),
             IP_CENTRAL_URLLC, str(PORTA_URLLC), str(intervalo_urllc), str(duracao_segundos)],
            stdout=open(arquivo_log, "w"),
            stderr=subprocess.STDOUT
        )
        leitores.append(LeitorIncremental(arquivo_log, "urllc-%s" % site["nome"]))
        processos_gerador_urllc.append(processo)

    print("*** Experimento em execução por %d segundos (saída em tempo real abaixo) ***" % duracao_segundos)
    monitorar_sinal_e_atuar(
        rede, duracao_segundos, leitores, controle_habilitado=(controle == "reativo")
    )

    for processo in processos_gerador_urllc:
        processo.wait()
    for processo in processos_cliente_iperf:
        processo.wait()
    time.sleep(2)  # dá tempo do monitor gravar o CSV final antes de analisar

    if not os.path.exists(ARQUIVO_LATENCIAS) or os.path.getsize(ARQUIVO_LATENCIAS) < 80:
        rede.stop()
        raise RuntimeError(
            "experimento inválido: nenhuma amostra uRLLC foi coletada; consulte %s" % caminho_log_monitor
        )

    partes_sufixo = []
    if sem_embb:
        partes_sufixo.append("sem_embb")
    else:
        partes_sufixo.append("embb_%s_%s" % (taxa_embb, tipo_embb))
        if controle != "nenhum":
            partes_sufixo.append(controle)
    sufixo = "_".join(partes_sufixo) if partes_sufixo else "experimento"

    print("*** Coletando estatísticas e gerando gráficos (sufixo: %s)" % sufixo)
    os.system(
        "%s %s %s %s %s --sufixo %s"
        % (CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "analisar_resultados.py"),
           ARQUIVO_LATENCIAS, ARQUIVO_EVENTOS, DIRETORIO_RESULTADOS, sufixo)
    )

    print("*** Experimento finalizado")
    rede.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Experimento closed loop uRLLC/eMBB sobre 4 switches OVS (adaptado para macOS via Docker)."
    )
    parser.add_argument("--duracao", type=int, default=60, help="Duração do experimento em segundos")
    parser.add_argument("--taxa-embb", type=str, default="12M", help="Taxa de bits por fluxo eMBB (ex.: 12M)")
    parser.add_argument("--tipo-embb", type=str, choices=["udp", "tcp"], default="udp")
    parser.add_argument("--controle", type=str, choices=["nenhum", "reativo"], default="reativo")
    parser.add_argument("--sem-embb", action="store_true", help="Roda uRLLC isolado, sem tráfego eMBB concorrente")
    parser.add_argument("--intervalo-urllc", type=float, default=0.1, help="Intervalo entre pacotes uRLLC (s)")
    parser.add_argument("--qos-estatico", action=argparse.BooleanOptionalAction, default=True,
                        help="Ativa/desativa classificação uRLLC em fila prioritária")
    parser.add_argument("--diretorio-saida", default=DIRETORIO_RESULTADOS,
                        help="Diretório isolado para CSVs, logs e gráficos desta execução")
    args = parser.parse_args()

    executar_experimento(
        duracao_segundos=args.duracao,
        taxa_embb=args.taxa_embb,
        tipo_embb=args.tipo_embb,
        controle=args.controle,
        sem_embb=args.sem_embb,
        intervalo_urllc=args.intervalo_urllc,
        qos_estatico=args.qos_estatico,
        diretorio_saida=args.diretorio_saida,
    )


if __name__ == "__main__":
    main()
