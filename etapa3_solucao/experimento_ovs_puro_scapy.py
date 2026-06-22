#!/usr/bin/env python3
"""
Experimento OVS puro + Scapy/TCP.

4 switches OVS em linha. O controle QoS e feito via OpenFlow:
- uRLLC usa fila de alta prioridade.
- eMBB pode ser descartado quando a latencia ultrapassa 5 ms.
"""

import argparse
import os
import subprocess
import sys
import time

DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIRETORIO_PROJETO)

from etapa3_solucao.topologia_ovs_puro_scapy import criar_topologia

DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_PROJETO, "docs", "resultados")
if not os.path.exists(DIRETORIO_RESULTADOS):
    os.makedirs(DIRETORIO_RESULTADOS)

ARQUIVO_SINAL = os.path.join(DIRETORIO_RESULTADOS, "sinal_controle_qos")
ARQUIVO_EVENTOS = os.path.join(DIRETORIO_RESULTADOS, "eventos_controle.txt")
ARQUIVO_LATENCIAS = os.path.join(DIRETORIO_RESULTADOS, "latencias_urllc.csv")

CAMINHO_PYTHON = "/root/atividade-final-redes-ppgti/.venv/bin/python3"


def registrar_evento(mensagem):
    with open(ARQUIVO_EVENTOS, "a") as arquivo:
        arquivo.write("%.3f\t%s\n" % (time.time(), mensagem))


def aplicar_controle_qos(rede, ativar):
    acao = "ativar" if ativar else "desativar"
    print("*** Aplicando controle QoS (OpenFlow): %s ***" % acao)
    registrar_evento("controle_%s" % acao)
    ofctl = "ovs-ofctl -O OpenFlow13"
    for nome_switch in ["r1", "r2", "r3", "r4"]:
        switch = rede.getNodeByName(nome_switch)
        if ativar:
            # Dropa trafego eMBB (UDP porta 5001) para proteger o uRLLC
            switch.cmd("%s add-flow %s 'priority=110,udp,tp_dst=5001,actions=drop'" % (ofctl, nome_switch))
            switch.cmd("%s add-flow %s 'priority=110,udp,tp_src=5001,actions=drop'" % (ofctl, nome_switch))
        else:
            switch.cmd("%s del-flows %s 'udp,tp_dst=5001'" % (ofctl, nome_switch))
            switch.cmd("%s del-flows %s 'udp,tp_src=5001'" % (ofctl, nome_switch))


def monitorar_sinal_e_atuar(rede, duracao_segundos):
    controle_ativo = False
    tempo_inicio = time.time()
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
        time.sleep(0.2)
    registrar_evento("fim_monitoramento")


def executar_experimento(duracao_segundos, taxa_embb, tipo_embb, controle, sem_embb,
                         intervalo_urllc, usar_scapy_otimizado=False):
    for arquivo in [ARQUIVO_EVENTOS, ARQUIVO_LATENCIAS, ARQUIVO_SINAL]:
        if os.path.exists(arquivo):
            os.remove(arquivo)

    rede = criar_topologia()

    h_urllc_a = rede.getNodeByName("h_urllc_a")
    h_urllc_b = rede.getNodeByName("h_urllc_b")
    h_embb_a = rede.getNodeByName("h_embb_a")
    h_embb_b = rede.getNodeByName("h_embb_b")

    if controle == "preventivo":
        print("*** Ativando controle preventivo (drop de eMBB desde o inicio)")
        aplicar_controle_qos(rede, True)

    if usar_scapy_otimizado:
        monitor_script = "monitor_controlador_scapy_otimizado.py"
        gerador_script = "gerador_urllc_scapy_otimizado.py"
    else:
        monitor_script = "monitor_controlador_scapy.py"
        gerador_script = "gerador_urllc_scapy.py"

    print("*** Iniciando monitor/controlador (%s) em h_urllc_b" % monitor_script)
    h_urllc_b.cmd("%s /root/atividade-final-redes-ppgti/etapa3_solucao/%s 10.0.3.2 5000 %d > /tmp/log_monitor.txt 2>&1 &"
                  % (CAMINHO_PYTHON, monitor_script, duracao_segundos))
    time.sleep(3)

    processo_cliente_iperf = None
    if not sem_embb:
        print("*** Iniciando servidor iperf em h_embb_b")
        h_embb_b.cmd("%s /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py servidor > /tmp/log_servidor_iperf.txt 2>&1 &"
                     % CAMINHO_PYTHON)
        time.sleep(2)

        print("*** Iniciando gerador de trafego eMBB em h_embb_a (%s %s)" % (taxa_embb, tipo_embb.upper()))
        processo_cliente_iperf = h_embb_a.popen(
            [CAMINHO_PYTHON, "/root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py",
             "cliente", "10.0.4.2", "5001", str(duracao_segundos), taxa_embb, tipo_embb],
            stdout=open("/tmp/log_cliente_iperf.txt", "w"),
            stderr=subprocess.STDOUT
        )
        time.sleep(3)
    else:
        print("*** Experimento SEM eMBB (uRLLC isolado)")
        registrar_evento("sem_embb")

    print("*** Iniciando gerador de trafego uRLLC (%s) em h_urllc_a (intervalo %.1fs)" % (gerador_script, intervalo_urllc))
    processo_gerador_urllc = h_urllc_a.popen(
        [CAMINHO_PYTHON, "/root/atividade-final-redes-ppgti/etapa3_solucao/%s" % gerador_script,
         "10.0.3.2", "5000", str(intervalo_urllc), str(duracao_segundos)],
        stdout=open("/tmp/log_gerador_urllc.txt", "w"),
        stderr=subprocess.STDOUT
    )

    print("*** Experimento em execucao por %d segundos" % duracao_segundos)
    monitorar_sinal_e_atuar(rede, duracao_segundos)

    processo_gerador_urllc.wait()
    if processo_cliente_iperf is not None:
        processo_cliente_iperf.wait()
    time.sleep(2)

    partes_sufixo = ["ovs_puro_scapy"]
    if sem_embb:
        partes_sufixo.append("sem_embb")
    else:
        partes_sufixo.append("embb_%s_%s" % (taxa_embb, tipo_embb))
        if controle != "nenhum":
            partes_sufixo.append(controle)
    caminho_grafico = os.path.join(DIRETORIO_RESULTADOS, "grafico_latencias_%s.png" % "_".join(partes_sufixo))

    print("*** Coletando resultados (%s)" % caminho_grafico)
    os.system("%s /root/atividade-final-redes-ppgti/etapa3_solucao/coletar_resultados.py %s %s %s"
              % (CAMINHO_PYTHON, ARQUIVO_LATENCIAS, caminho_grafico, ARQUIVO_EVENTOS))

    print("*** Experimento finalizado")
    rede.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Experimento OVS puro + Scapy/TCP para uRLLC <= 5 ms."
    )
    parser.add_argument("--duracao", type=int, default=60)
    parser.add_argument("--taxa-embb", type=str, default="3M")
    parser.add_argument("--tipo-embb", type=str, choices=["udp", "tcp"], default="udp")
    parser.add_argument("--controle", type=str, choices=["nenhum", "preventivo", "reativo"], default="nenhum")
    parser.add_argument("--sem-embb", action="store_true")
    parser.add_argument("--intervalo-urllc", type=float, default=0.5)
    parser.add_argument("--scapy", action="store_true",
                        help="Usa gerador/monitor Scapy padrao.")
    parser.add_argument("--scapy-otimizado", action="store_true",
                        help="Usa gerador/monitor Scapy otimizado.")
    args = parser.parse_args()

    if args.scapy and args.scapy_otimizado:
        parser.error("--scapy e --scapy-otimizado sao mutuamente exclusivos.")

    executar_experimento(
        duracao_segundos=args.duracao,
        taxa_embb=args.taxa_embb,
        tipo_embb=args.tipo_embb,
        controle=args.controle,
        sem_embb=args.sem_embb,
        intervalo_urllc=args.intervalo_urllc,
        usar_scapy_otimizado=args.scapy_otimizado
    )


if __name__ == "__main__":
    main()
