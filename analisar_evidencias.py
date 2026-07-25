#!/usr/bin/env python3
"""Consolida perdas uRLLC e vazão eMBB para a seção de Avaliação.

O CSV de latência contém apenas mensagens recebidas. Por isso, este script
combina as latências recebidas com os contadores de tentativas/falhas dos
geradores uRLLC e calcula também a taxa efetiva de não conformidade:

    (timeouts + latências acima de 5 ms) / tentativas

Além disso, extrai a vazão e a perda UDP das linhas finais do iperf3. As
estatísticas de intervalo de confiança usam a execução completa como unidade
independente, e não cada pacote individual.
"""

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


LIMIAR_LATENCIA_MS = 5.0
SCENARIOS = (
    ("isolado", "Isolado"),
    ("sem_qos", "Sem QoS"),
    ("qos_estatico", "QoS estático"),
    ("reativo", "Closed loop"),
)
SITE_NAMES = {
    "biblioteca": "Biblioteca",
    "laboratorios": "Laboratorios",
    "reitoria": "Reitoria",
}
# O nome do site no CSV/métrica é "Laboratorios", mas o orquestrador usa
# "labs" no nome do arquivo iperf3.
EMBB_LOG_SITES = (
    ("biblioteca", "Biblioteca"),
    ("labs", "Laboratorios"),
    ("reitoria", "Reitoria"),
)
IPERF_UNITS_TO_MBIT = {
    "Kbits/sec": 0.001,
    "Mbits/sec": 1.0,
    "Gbits/sec": 1000.0,
}


def intervalo_95(valores):
    """Calcula IC 95% da média usando as repetições independentes."""
    valores = np.asarray(valores, dtype=float)
    if len(valores) < 2:
        return float("nan"), float("nan")
    erro_padrao = stats.sem(valores)
    return tuple(float(v) for v in stats.t.interval(
        0.95, df=len(valores) - 1, loc=float(np.mean(valores)), scale=erro_padrao
    ))


def ler_pares_chave_valor(caminho):
    valores = {}
    with caminho.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            if "=" not in linha:
                continue
            chave, valor = linha.rstrip("\n").split("=", 1)
            valores[chave] = valor
    return valores


def ler_latencias_por_site(caminho):
    resultado = defaultdict(lambda: {"recebidas": 0, "violacoes": 0})
    if not caminho.exists():
        return resultado
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            site = linha.get("site", "desconhecido")
            resultado[site]["recebidas"] += 1
            if float(linha["latencia_ms"]) > LIMIAR_LATENCIA_MS:
                resultado[site]["violacoes"] += 1
    return resultado


def descobrir_repeticoes(diretorio, nome_cenario):
    pasta = diretorio / "execucoes" / nome_cenario
    return sorted(
        (caminho for caminho in pasta.glob("rep_*") if caminho.is_dir()),
        key=lambda caminho: caminho.name,
    )


def coletar_metricas_urllc(diretorio):
    linhas = []
    for nome_cenario, rotulo in SCENARIOS:
        for pasta_rep in descobrir_repeticoes(diretorio, nome_cenario):
            numero_rep = pasta_rep.name.removeprefix("rep_")
            por_site = ler_latencias_por_site(pasta_rep / "latencias_urllc.csv")
            for caminho_metricas in sorted(pasta_rep.glob("metricas_urllc_*.txt")):
                identificador = caminho_metricas.stem.removeprefix("metricas_urllc_")
                site = SITE_NAMES.get(identificador, identificador)
                dados = ler_pares_chave_valor(caminho_metricas)
                tentativas = int(dados.get("tentativas", 0))
                sucessos = int(dados.get("sucessos", 0))
                falhas = int(dados.get("falhas", tentativas - sucessos))
                recebidas = int(por_site.get(site, {}).get("recebidas", 0))
                violacoes = int(por_site.get(site, {}).get("violacoes", 0))
                nao_conformes = falhas + violacoes
                linhas.append({
                    "cenario": nome_cenario,
                    "cenario_rotulo": rotulo,
                    "repeticao": numero_rep,
                    "site": site,
                    "tentativas": tentativas,
                    "sucessos": sucessos,
                    "falhas": falhas,
                    "recebidas": recebidas,
                    "violacoes_5ms": violacoes,
                    "nao_conformes": nao_conformes,
                    "taxa_perdas": 100.0 * falhas / tentativas if tentativas else 0.0,
                    "taxa_nao_conforme": 100.0 * nao_conformes / tentativas if tentativas else 0.0,
                })

    caminho_csv = diretorio / "metricas_urllc.csv"
    campos = (
        "cenario", "repeticao", "site", "tentativas", "sucessos", "falhas",
        "recebidas", "violacoes_5ms", "nao_conformes", "taxa_perdas",
        "taxa_nao_conforme",
    )
    with caminho_csv.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({campo: linha[campo] for campo in campos})

    por_execucao = defaultdict(lambda: defaultdict(int))
    for linha in linhas:
        chave = (linha["cenario"], linha["repeticao"])
        for campo in ("tentativas", "sucessos", "falhas", "recebidas", "violacoes_5ms", "nao_conformes"):
            por_execucao[chave][campo] += linha[campo]

    caminho_tabela = diretorio / "metricas_urllc_tabela.txt"
    resumo = {}
    with caminho_tabela.open("w", encoding="utf-8") as arquivo:
        arquivo.write("Métricas de conformidade uRLLC (limiar: 5 ms)\n")
        arquivo.write("A não conformidade inclui timeouts/perdas e latências recebidas acima de 5 ms.\n\n")
        arquivo.write(
            "%-20s %5s %11s %10s %12s %14s %12s %18s %18s\n"
            % ("Cenário", "reps", "Tentativas", "Falhas", "Violações", "Não conformes", "Perdas %", "Não conformes %", "IC95 não conf. %")
        )
        arquivo.write("-" * 139 + "\n")
        for nome_cenario, rotulo in SCENARIOS:
            execucoes = [
                valores for (cenario, _), valores in por_execucao.items()
                if cenario == nome_cenario
            ]
            if not execucoes:
                continue
            taxas_perdas = [100.0 * e["falhas"] / e["tentativas"] for e in execucoes if e["tentativas"]]
            taxas_nao_conformes = [100.0 * e["nao_conformes"] / e["tentativas"] for e in execucoes if e["tentativas"]]
            tentativas = sum(e["tentativas"] for e in execucoes)
            falhas = sum(e["falhas"] for e in execucoes)
            violacoes = sum(e["violacoes_5ms"] for e in execucoes)
            nao_conformes = sum(e["nao_conformes"] for e in execucoes)
            perda_pooled = 100.0 * falhas / tentativas if tentativas else float("nan")
            nao_conf_pooled = 100.0 * nao_conformes / tentativas if tentativas else float("nan")
            ic_inferior, ic_superior = intervalo_95(taxas_nao_conformes)
            if math.isfinite(ic_inferior):
                ic_inferior = max(0.0, min(100.0, ic_inferior))
            if math.isfinite(ic_superior):
                ic_superior = max(0.0, min(100.0, ic_superior))
            resumo[nome_cenario] = {
                "repeticoes": len(execucoes),
                "taxas_perdas": taxas_perdas,
                "taxas_nao_conformes": taxas_nao_conformes,
            }
            arquivo.write(
                "%-20s %5d %11d %10d %12d %14d %12.2f %18.2f [%7.2f, %7.2f]\n"
                % (
                    rotulo, len(execucoes), tentativas, falhas, violacoes,
                    nao_conformes, perda_pooled, nao_conf_pooled,
                    ic_inferior, ic_superior,
                )
            )

    if resumo:
        nomes = [rotulo for nome, rotulo in SCENARIOS if nome in resumo]
        valores_perdas = [
            float(np.mean(resumo[nome]["taxas_perdas"])) if resumo[nome]["taxas_perdas"] else 0.0
            for nome, _ in SCENARIOS if nome in resumo
        ]
        valores_nao_conformes = [
            float(np.mean(resumo[nome]["taxas_nao_conformes"])) if resumo[nome]["taxas_nao_conformes"] else 0.0
            for nome, _ in SCENARIOS if nome in resumo
        ]
        fig, eixos = plt.subplots(1, 2, figsize=(13, 5))
        for eixo, valores, titulo in (
            (eixos[0], valores_perdas, "Perdas/timeouts uRLLC"),
            (eixos[1], valores_nao_conformes, "Não conformidade uRLLC"),
        ):
            eixo.bar(nomes, valores, color="tab:orange", alpha=0.8)
            eixo.set_ylabel("Percentual das tentativas (%)")
            eixo.set_title(titulo)
            eixo.tick_params(axis="x", rotation=15)
            eixo.grid(True, alpha=0.3, axis="y")
        fig.suptitle("Conformidade uRLLC por cenário")
        fig.tight_layout()
        fig.savefig(diretorio / "metricas_urllc.png", dpi=160)
        plt.close(fig)

    return linhas


def extrair_linha_receiver(caminho):
    padrao = re.compile(
        r"([0-9]+(?:\.[0-9]+)?)\s+(Kbits/sec|Mbits/sec|Gbits/sec).*?"
        r"\(([0-9]+(?:\.[0-9]+)?)%\)\s+receiver\s*$"
    )
    with caminho.open(encoding="utf-8", errors="replace") as arquivo:
        for linha in reversed(arquivo.readlines()):
            correspondencia = padrao.search(linha.strip())
            if correspondencia:
                valor, unidade, perda = correspondencia.groups()
                return {
                    "vazao_mbit_s": float(valor) * IPERF_UNITS_TO_MBIT[unidade],
                    "perda_percentual": float(perda),
                }
    return None


def coletar_vazao_embb(diretorio):
    linhas = []
    for nome_cenario, rotulo in SCENARIOS:
        if nome_cenario == "isolado":
            continue
        for pasta_rep in descobrir_repeticoes(diretorio, nome_cenario):
            numero_rep = pasta_rep.name.removeprefix("rep_")
            for identificador, site in EMBB_LOG_SITES:
                caminho = pasta_rep / ("embb_%s.log" % identificador)
                if not caminho.exists():
                    continue
                resultado = extrair_linha_receiver(caminho)
                if resultado is None:
                    continue
                linhas.append({
                    "cenario": nome_cenario,
                    "cenario_rotulo": rotulo,
                    "repeticao": numero_rep,
                    "site": site,
                    **resultado,
                })

    campos = ("cenario", "repeticao", "site", "vazao_mbit_s", "perda_percentual")
    with (diretorio / "vazao_embb.csv").open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({campo: linha[campo] for campo in campos})

    por_execucao = defaultdict(list)
    for linha in linhas:
        por_execucao[(linha["cenario"], linha["repeticao"])].append(linha)

    caminho_tabela = diretorio / "vazao_embb_tabela.txt"
    resumo = {}
    with caminho_tabela.open("w", encoding="utf-8") as arquivo:
        arquivo.write("Vazão eMBB recebida (extraída da linha final receiver do iperf3)\n\n")
        arquivo.write(
            "%-20s %5s %12s %16s %12s %12s %18s\n"
            % ("Cenário", "reps", "sites", "Média Mbit/s", "DesvPad", "Perda média %", "IC95 vazão")
        )
        arquivo.write("-" * 108 + "\n")
        for nome_cenario, rotulo in SCENARIOS:
            execucoes = [linhas_rep for (cenario, _), linhas_rep in por_execucao.items() if cenario == nome_cenario]
            if not execucoes:
                continue
            medias_rep = [float(np.mean([linha["vazao_mbit_s"] for linha in linhas_rep])) for linhas_rep in execucoes if linhas_rep]
            perdas_rep = [float(np.mean([linha["perda_percentual"] for linha in linhas_rep])) for linhas_rep in execucoes if linhas_rep]
            ic_inferior, ic_superior = intervalo_95(medias_rep)
            resumo[nome_cenario] = medias_rep
            arquivo.write(
                "%-20s %5d %12d %16.3f %12.3f %12.2f [%7.3f, %7.3f]\n"
                % (
                    rotulo, len(execucoes), sum(len(linhas_rep) for linhas_rep in execucoes),
                    float(np.mean(medias_rep)) if medias_rep else float("nan"),
                    float(np.std(medias_rep, ddof=1)) if len(medias_rep) > 1 else float("nan"),
                    float(np.mean(perdas_rep)) if perdas_rep else float("nan"),
                    ic_inferior, ic_superior,
                )
            )

    if resumo:
        nomes = [rotulo for nome, rotulo in SCENARIOS if nome in resumo]
        medias = [float(np.mean(resumo[nome])) for nome, _ in SCENARIOS if nome in resumo]
        inferiores = []
        superiores = []
        for nome, _ in SCENARIOS:
            if nome not in resumo:
                continue
            baixo, alto = intervalo_95(resumo[nome])
            media = float(np.mean(resumo[nome]))
            inferiores.append(0.0 if not math.isfinite(baixo) else media - baixo)
            superiores.append(0.0 if not math.isfinite(alto) else alto - media)
        fig, eixo = plt.subplots(figsize=(9, 5))
        eixo.bar(nomes, medias, yerr=[inferiores, superiores], capsize=5, color="tab:green", alpha=0.8)
        eixo.set_ylabel("Vazão recebida (Mbit/s)")
        eixo.set_title("Vazão eMBB por cenário (IC 95% entre repetições)")
        eixo.tick_params(axis="x", rotation=15)
        eixo.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(diretorio / "vazao_embb.png", dpi=160)
        plt.close(fig)

    return linhas


def main():
    parser = argparse.ArgumentParser(description="Consolida perdas uRLLC e vazão eMBB.")
    parser.add_argument("--resultados", default="resultados", help="Diretório da bateria experimental")
    args = parser.parse_args()
    diretorio = Path(args.resultados).resolve()
    coletar_metricas_urllc(diretorio)
    coletar_vazao_embb(diretorio)
    print("Métricas uRLLC e vazão eMBB consolidadas em %s" % diretorio)


if __name__ == "__main__":
    main()
