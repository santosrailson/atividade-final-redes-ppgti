#!/usr/bin/env python3
"""
Orquestrador do experimento closed loop uRLLC x eMBB sobre 4 switches OVS.

Fluxo de um experimento:

1. Sobe a topologia (topologia.py).
2. (Opcional) Ativa o controle QoS preventivamente, já descartando
   eMBB desde o início.
3. Inicia o monitor/controlador no host de destino uRLLC
   (monitor_controlador.py).
4. Inicia o servidor + cliente iperf3 do eMBB (gerador_embb.py), a
   menos que o experimento seja "uRLLC isolado" (--sem-embb).
5. Inicia o gerador de tráfego uRLLC (gerador_urllc.py).
6. Fica observando o arquivo de sinal escrito pelo monitor e, quando
   necessário, instala/remove via OpenFlow a regra que derruba o
   tráfego eMBB -- fechando o laço de controle (closed loop).
7. Ao final, chama analisar_resultados.py para gerar estatísticas e
   os gráficos usados no artigo.

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

from topologia import criar_topologia

DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_PROJETO, "resultados")
os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)

ARQUIVO_SINAL = os.path.join(DIRETORIO_RESULTADOS, "sinal_controle_qos")
ARQUIVO_EVENTOS = os.path.join(DIRETORIO_RESULTADOS, "eventos_controle.txt")
ARQUIVO_LATENCIAS = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc.csv")

# Usa sempre o mesmo interpretador Python que executou este script
# (o do venv/imagem Docker), em vez de um caminho fixo.
CAMINHO_PYTHON = sys.executable


def registrar_evento(mensagem):
    with open(ARQUIVO_EVENTOS, "a") as arquivo:
        arquivo.write("%.3f\t%s\n" % (time.time(), mensagem))


def aplicar_controle_qos(rede, ativar):
    """Instala ou remove, via OpenFlow, a regra que descarta o tráfego
    eMBB (UDP porta 5001). É a ação de atuação do closed loop sobre os
    4 switches OVS que representam a rede de transporte."""
    acao = "ativar" if ativar else "desativar"
    print("*** Aplicando controle QoS (OpenFlow): %s ***" % acao)
    registrar_evento("controle_%s" % acao)
    ofctl = "ovs-ofctl -O OpenFlow13"
    for nome_switch in ["r1", "r2", "r3", "r4"]:
        switch = rede.getNodeByName(nome_switch)
        if ativar:
            switch.cmd("%s add-flow %s 'priority=110,udp,tp_dst=5001,actions=drop'" % (ofctl, nome_switch))
            switch.cmd("%s add-flow %s 'priority=110,udp,tp_src=5001,actions=drop'" % (ofctl, nome_switch))
        else:
            switch.cmd("%s del-flows %s 'udp,tp_dst=5001'" % (ofctl, nome_switch))
            switch.cmd("%s del-flows %s 'udp,tp_src=5001'" % (ofctl, nome_switch))


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


def monitorar_sinal_e_atuar(rede, duracao_segundos, leitores):
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

            if sinal == "ativar" and not controle_ativo:
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


def executar_experimento(duracao_segundos, taxa_embb, tipo_embb, controle, sem_embb, intervalo_urllc):
    for arquivo in [ARQUIVO_EVENTOS, ARQUIVO_LATENCIAS, ARQUIVO_SINAL]:
        if os.path.exists(arquivo):
            os.remove(arquivo)

    rede = criar_topologia()

    h_urllc_a = rede.getNodeByName("h_urllc_a")
    h_urllc_b = rede.getNodeByName("h_urllc_b")
    h_embb_a = rede.getNodeByName("h_embb_a")
    h_embb_b = rede.getNodeByName("h_embb_b")

    if controle == "preventivo":
        print("*** Ativando controle preventivo (drop de eMBB desde o início)")
        aplicar_controle_qos(rede, True)

    leitores = [LeitorIncremental("/tmp/log_monitor.txt", "monitor")]

    print("*** Iniciando monitor/controlador em h_urllc_b")
    h_urllc_b.cmd(
        "%s %s 10.0.3.2 5000 %d > /tmp/log_monitor.txt 2>&1 &"
        % (CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "monitor_controlador.py"), duracao_segundos)
    )
    time.sleep(3)  # dá tempo do monitor abrir o socket de escuta antes do gerador conectar

    processo_cliente_iperf = None
    if not sem_embb:
        print("*** Iniciando servidor iperf3 em h_embb_b")
        h_embb_b.cmd(
            "%s %s servidor > /tmp/log_servidor_iperf.txt 2>&1 &"
            % (CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_embb.py"))
        )
        time.sleep(2)

        print("*** Iniciando gerador de tráfego eMBB em h_embb_a (%s %s)" % (taxa_embb, tipo_embb.upper()))
        processo_cliente_iperf = h_embb_a.popen(
            [CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_embb.py"),
             "cliente", "10.0.4.2", "5001", str(duracao_segundos), taxa_embb, tipo_embb],
            stdout=open("/tmp/log_cliente_iperf.txt", "w"),
            stderr=subprocess.STDOUT
        )
        leitores.append(LeitorIncremental("/tmp/log_cliente_iperf.txt", "embb"))
        time.sleep(3)
    else:
        print("*** Experimento SEM eMBB (uRLLC isolado)")
        registrar_evento("sem_embb")

    print("*** Iniciando gerador de tráfego uRLLC em h_urllc_a (intervalo %.1fs)" % intervalo_urllc)
    processo_gerador_urllc = h_urllc_a.popen(
        [CAMINHO_PYTHON, os.path.join(DIRETORIO_PROJETO, "gerador_urllc.py"),
         "10.0.3.2", "5000", str(intervalo_urllc), str(duracao_segundos)],
        stdout=open("/tmp/log_gerador_urllc.txt", "w"),
        stderr=subprocess.STDOUT
    )
    leitores.append(LeitorIncremental("/tmp/log_gerador_urllc.txt", "urllc"))

    print("*** Experimento em execução por %d segundos (saída em tempo real abaixo) ***" % duracao_segundos)
    monitorar_sinal_e_atuar(rede, duracao_segundos, leitores)

    processo_gerador_urllc.wait()
    if processo_cliente_iperf is not None:
        processo_cliente_iperf.wait()
    time.sleep(2)  # dá tempo do monitor gravar o CSV final antes de analisar

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
    parser.add_argument("--taxa-embb", type=str, default="5M", help="Taxa de bits do tráfego eMBB (ex.: 5M, 10M)")
    parser.add_argument("--tipo-embb", type=str, choices=["udp", "tcp"], default="udp")
    parser.add_argument("--controle", type=str, choices=["nenhum", "preventivo", "reativo"], default="reativo")
    parser.add_argument("--sem-embb", action="store_true", help="Roda uRLLC isolado, sem tráfego eMBB concorrente")
    parser.add_argument("--intervalo-urllc", type=float, default=0.1, help="Intervalo entre pacotes uRLLC (s)")
    args = parser.parse_args()

    executar_experimento(
        duracao_segundos=args.duracao,
        taxa_embb=args.taxa_embb,
        tipo_embb=args.tipo_embb,
        controle=args.controle,
        sem_embb=args.sem_embb,
        intervalo_urllc=args.intervalo_urllc,
    )


if __name__ == "__main__":
    main()
