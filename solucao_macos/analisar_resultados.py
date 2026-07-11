#!/usr/bin/env python3
"""
Análise estatística dos resultados de um experimento uRLLC.

Lê o CSV de latências one-way (gerado por monitor_controlador.py) e o
arquivo de eventos de controle (gerado por experimento.py) e produz:

  1. resumo_estatistico_<sufixo>.txt
       Estatísticas descritivas clássicas (média, mediana, desvio
       padrão, percentis, intervalo de confiança de 95% para a média)
       e a taxa de violação do limiar de 5 ms.

  2. grafico_serie_temporal_<sufixo>.png
       Latência amostra-a-amostra ao longo do experimento, com a
       linha do limiar de 5 ms e marcações de quando o controle
       closed loop ligou/desligou. Mostra o EFEITO do controle no
       tempo (ex.: latência cai logo após o controle ser ativado).

  3. grafico_histograma_<sufixo>.png
       Distribuição das latências (forma, dispersão, cauda longa
       típica de filas). Média e mediana marcadas para evidenciar
       assimetria (quando média > mediana, há cauda longa à direita).

  4. grafico_boxplot_<sufixo>.png
       Resumo visual de mediana, quartis e outliers -- útil para
       comparar visualmente vários cenários lado a lado (ver também
       comparar_cenarios.py).

  5. grafico_cdf_<sufixo>.png
       Função de distribuição cumulativa empírica (ECDF): para cada
       latência x, mostra a fração de amostras <= x. É a forma mais
       direta de ler "qual % das amostras ficou abaixo de 5 ms?" e de
       localizar percentis (p50, p90, p95, p99) -- métricas-padrão em
       SLAs de redes 5G/uRLLC.

Todos os gráficos usam o backend "Agg" do Matplotlib (sem interface
gráfica), pois rodam dentro do container Docker sem display.
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

LIMIAR_LATENCIA_MS = 5.0
NIVEL_CONFIANCA = 0.95


def ler_amostras(caminho_csv):
    valores = []
    timestamps = []
    if not os.path.exists(caminho_csv):
        return np.array(valores), np.array(timestamps)
    with open(caminho_csv, "r", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        for indice, linha in enumerate(leitor):
            if not linha:
                continue
            valores.append(float(linha["latencia_ms"]))
            timestamps.append(float(linha.get("timestamp_recebimento") or indice))
    return np.array(valores), np.array(timestamps)


def ler_latencias(caminho_csv):
    return ler_amostras(caminho_csv)[0]


def ler_eventos(caminho_eventos):
    eventos = []
    if not os.path.exists(caminho_eventos):
        return eventos
    with open(caminho_eventos, "r") as arquivo:
        for linha in arquivo:
            partes = linha.strip().split("\t")
            if len(partes) == 2:
                eventos.append((float(partes[0]), partes[1]))
    return eventos


def calcular_estatisticas(valores):
    """Calcula as métricas descritivas usadas no artigo.

    O intervalo de confiança de 95% para a média usa a distribuição t
    de Student (mais apropriada que a normal quando a amostra é
    pequena/finita e o desvio padrão populacional é desconhecido).
    """
    if len(valores) == 0:
        return None

    n = len(valores)
    media = float(np.mean(valores))
    mediana = float(np.median(valores))
    desvio_padrao = float(np.std(valores, ddof=1)) if n > 1 else 0.0
    minimo = float(np.min(valores))
    maximo = float(np.max(valores))
    percentis = {p: float(np.percentile(valores, p)) for p in (50, 75, 90, 95, 99)}
    violacoes = int(np.sum(valores > LIMIAR_LATENCIA_MS))
    percentual_violacoes = 100.0 * violacoes / n

    if n > 1:
        erro_padrao = stats.sem(valores)
        ic_inferior, ic_superior = stats.t.interval(
            NIVEL_CONFIANCA, df=n - 1, loc=media, scale=erro_padrao
        )
    else:
        ic_inferior, ic_superior = media, media

    return {
        "n": n, "media": media, "mediana": mediana, "desvio_padrao": desvio_padrao,
        "minimo": minimo, "maximo": maximo, "percentis": percentis,
        "violacoes": violacoes, "percentual_violacoes": percentual_violacoes,
        "ic_95_inferior": float(ic_inferior), "ic_95_superior": float(ic_superior),
    }


def escrever_resumo(estatisticas, caminho_saida, sufixo):
    with open(caminho_saida, "w") as arquivo:
        arquivo.write("=== Resumo estatístico do experimento: %s ===\n\n" % sufixo)
        if estatisticas is None:
            arquivo.write("Nenhuma amostra de latência encontrada.\n")
            return

        e = estatisticas
        arquivo.write("Amostras coletadas: %d\n" % e["n"])
        arquivo.write("Latência média: %.3f ms\n" % e["media"])
        arquivo.write("Latência mediana (p50): %.3f ms\n" % e["mediana"])
        arquivo.write("Desvio padrão: %.3f ms\n" % e["desvio_padrao"])
        arquivo.write("Mínimo: %.3f ms | Máximo: %.3f ms\n" % (e["minimo"], e["maximo"]))
        arquivo.write(
            "Intervalo de confiança 95%% para a média: [%.3f, %.3f] ms\n"
            % (e["ic_95_inferior"], e["ic_95_superior"])
        )
        arquivo.write("\nPercentis:\n")
        for p, valor in e["percentis"].items():
            arquivo.write("  p%d: %.3f ms\n" % (p, valor))
        arquivo.write(
            "\nViolações do limiar de %.1f ms: %d de %d amostras (%.2f%%)\n"
            % (LIMIAR_LATENCIA_MS, e["violacoes"], e["n"], e["percentual_violacoes"])
        )


def gerar_grafico_serie_temporal(latencias, timestamps, eventos, caminho_saida):
    plt.figure(figsize=(12, 6))
    plt.plot(latencias, marker="o", markersize=3, linestyle="-", linewidth=1, color="tab:blue", label="Latência uRLLC")
    plt.axhline(y=LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")

    rotulos_usados = set()
    for timestamp, evento in eventos:
        indice = int(np.searchsorted(timestamps, timestamp)) if len(timestamps) else -1
        if not (0 <= indice < len(latencias)):
            continue
        if evento == "controle_ativar":
            rotulo = "Controle ativado" if "ativado" not in rotulos_usados else None
            plt.axvline(x=indice, color="green", linestyle=":", alpha=0.7, label=rotulo)
            rotulos_usados.add("ativado")
        elif evento == "controle_desativar":
            rotulo = "Controle desativado" if "desativado" not in rotulos_usados else None
            plt.axvline(x=indice, color="orange", linestyle=":", alpha=0.7, label=rotulo)
            rotulos_usados.add("desativado")

    plt.xlabel("Amostra (ordem de chegada)")
    plt.ylabel("Latência one-way (ms)")
    plt.title("Latência uRLLC ao longo do experimento")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def gerar_grafico_histograma(latencias, estatisticas, caminho_saida):
    plt.figure(figsize=(10, 6))
    plt.hist(latencias, bins=30, color="tab:blue", alpha=0.75, edgecolor="black")
    plt.axvline(estatisticas["media"], color="red", linestyle="-", label="Média (%.2f ms)" % estatisticas["media"])
    plt.axvline(estatisticas["mediana"], color="green", linestyle="--", label="Mediana (%.2f ms)" % estatisticas["mediana"])
    plt.axvline(LIMIAR_LATENCIA_MS, color="black", linestyle=":", label="Limiar de 5 ms")
    plt.xlabel("Latência one-way (ms)")
    plt.ylabel("Frequência (número de amostras)")
    plt.title("Distribuição das latências uRLLC")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def gerar_grafico_boxplot(latencias, sufixo, caminho_saida):
    plt.figure(figsize=(6, 6))
    # Ticks definidos manualmente (em vez do parâmetro labels/tick_labels
    # do boxplot, cujo nome mudou entre versões do Matplotlib) para
    # manter compatibilidade tanto com Matplotlib < 3.9 quanto >= 3.9.
    caixa = plt.boxplot(latencias, showmeans=True, patch_artist=True)
    plt.xticks([1], [sufixo])
    for patch in caixa["boxes"]:
        patch.set_facecolor("tab:blue")
        patch.set_alpha(0.6)
    plt.axhline(y=LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")
    plt.ylabel("Latência one-way (ms)")
    plt.title("Mediana, quartis e outliers de latência")
    plt.legend()
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def gerar_grafico_cdf(latencias, estatisticas, caminho_saida):
    valores_ordenados = np.sort(latencias)
    fracao_acumulada = np.arange(1, len(valores_ordenados) + 1) / len(valores_ordenados)

    plt.figure(figsize=(10, 6))
    plt.plot(valores_ordenados, fracao_acumulada, color="tab:blue", linewidth=2, label="ECDF (empírica)")
    plt.axvline(LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")

    for p in (50, 90, 95, 99):
        valor = estatisticas["percentis"].get(p) if p in estatisticas["percentis"] else np.percentile(latencias, p)
        plt.plot(valor, p / 100.0, "ko", markersize=4)
        plt.annotate("p%d = %.2f ms" % (p, valor), (valor, p / 100.0),
                     textcoords="offset points", xytext=(6, -4), fontsize=8)

    plt.xlabel("Latência one-way (ms)")
    plt.ylabel("Fração acumulada de amostras")
    plt.title("Função de distribuição cumulativa empírica (ECDF) da latência")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def analisar(caminho_csv, caminho_eventos, diretorio_saida, sufixo):
    os.makedirs(diretorio_saida, exist_ok=True)
    latencias, timestamps = ler_amostras(caminho_csv)
    eventos = ler_eventos(caminho_eventos)
    estatisticas = calcular_estatisticas(latencias)

    caminho_resumo = os.path.join(diretorio_saida, "resumo_estatistico_%s.txt" % sufixo)
    escrever_resumo(estatisticas, caminho_resumo, sufixo)
    print(open(caminho_resumo).read())

    if estatisticas is None:
        print("Nenhuma latência para plotar -- gráficos não gerados.")
        return

    gerar_grafico_serie_temporal(
        latencias, timestamps, eventos, os.path.join(diretorio_saida, "grafico_serie_temporal_%s.png" % sufixo)
    )
    gerar_grafico_histograma(
        latencias, estatisticas, os.path.join(diretorio_saida, "grafico_histograma_%s.png" % sufixo)
    )
    gerar_grafico_boxplot(
        latencias, sufixo, os.path.join(diretorio_saida, "grafico_boxplot_%s.png" % sufixo)
    )
    gerar_grafico_cdf(
        latencias, estatisticas, os.path.join(diretorio_saida, "grafico_cdf_%s.png" % sufixo)
    )
    print("Gráficos salvos em %s (sufixo: %s)" % (diretorio_saida, sufixo))


def main():
    parser = argparse.ArgumentParser(
        description="Gera estatísticas e gráficos a partir das latências uRLLC de um experimento."
    )
    parser.add_argument("caminho_csv", help="CSV de latências (latencias_urllc.csv)")
    parser.add_argument("caminho_eventos", help="Arquivo de eventos de controle (eventos_controle.txt)")
    parser.add_argument("diretorio_saida", help="Pasta onde salvar os gráficos e o resumo")
    parser.add_argument("--sufixo", default="experimento", help="Sufixo usado nos nomes dos arquivos gerados")
    args = parser.parse_args()

    analisar(args.caminho_csv, args.caminho_eventos, args.diretorio_saida, args.sufixo)


if __name__ == "__main__":
    main()
