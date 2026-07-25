#!/usr/bin/env python3
"""
Compara estatisticamente vários cenários de experimento (ex.: uRLLC
isolado x uRLLC+eMBB sem QoS x QoS estático x closed loop reativo).

Este script é o que dá suporte direto à seção de "Avaliação" do
artigo: em vez de olhar um experimento por vez, gera uma tabela e
gráficos colocando todos os cenários lado a lado, deixando visível o
ganho (ou não) trazido pelo controle closed loop.

Uso típico (depois de rodar alguns experimentos com experimento.py,
renomeando/copiando o latencias_urllc.csv de cada um):

    python3 comparar_cenarios.py \\
        --cenario "Isolado:resultados/latencias_isolado.csv" \\
        --cenario "Sem QoS:resultados/latencias_sem_qos.csv" \\
        --cenario "QoS estático:resultados/latencias_qos_estatico.csv" \\
        --cenario "Closed loop:resultados/latencias_reativo.csv" \\
        --saida resultados/comparacao

O script executar_bateria_testes.sh automatiza essa sequência.
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

LIMIAR_LATENCIA_MS = 5.0
NIVEL_CONFIANCA = 0.95


def ler_latencias(caminho_csv):
    valores = []
    if not os.path.exists(caminho_csv):
        return np.array(valores)
    with open(caminho_csv, "r", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha:
                valores.append(float(linha["latencia_ms"]))
    return np.array(valores)


def calcular_estatisticas(repeticoes):
    if isinstance(repeticoes, np.ndarray):
        repeticoes = [repeticoes]
    repeticoes = [valores for valores in repeticoes if len(valores) > 0]
    valores = np.concatenate(repeticoes) if repeticoes else np.array([])
    n = len(valores)
    if n == 0:
        return None
    medias_repeticoes = np.array([np.mean(amostras) for amostras in repeticoes])
    # A média e o IC devem usar as execuções independentes como unidade
    # experimental. Os pacotes continuam sendo usados para percentis e para
    # descrever a distribuição agregada, mas não como réplicas independentes.
    media = float(np.mean(medias_repeticoes))
    erro_padrao = stats.sem(medias_repeticoes) if len(medias_repeticoes) > 1 else 0.0
    if len(medias_repeticoes) > 1:
        ic_inferior, ic_superior = stats.t.interval(
            NIVEL_CONFIANCA, df=len(medias_repeticoes) - 1,
            loc=float(np.mean(medias_repeticoes)), scale=erro_padrao
        )
    else:
        ic_inferior, ic_superior = float("nan"), float("nan")
    if np.isfinite(ic_inferior):
        ic_inferior = max(0.0, float(ic_inferior))
    if np.isfinite(ic_superior):
        ic_superior = max(0.0, float(ic_superior))
    return {
        "n": n,
        "repeticoes": len(repeticoes),
        "media": media,
        "mediana": float(np.median(valores)),
        "desvio_padrao": float(np.std(valores, ddof=1)) if n > 1 else 0.0,
        "p95": float(np.percentile(valores, 95)),
        "p99": float(np.percentile(valores, 99)),
        "percentual_violacoes": 100.0 * float(np.sum(valores > LIMIAR_LATENCIA_MS)) / n,
        "ic_95_inferior": float(ic_inferior),
        "ic_95_superior": float(ic_superior),
    }


def escrever_tabela(cenarios_estatisticas, caminho_saida):
    with open(caminho_saida, "w") as arquivo:
        cabecalho = "%-20s %5s %7s %10s %10s %10s %10s %10s %12s %23s" % (
            "Cenário", "reps", "n", "Média", "Mediana", "DesvPad", "p95", "p99", "%>5ms", "IC95 média"
        )
        arquivo.write(cabecalho + "\n")
        arquivo.write("-" * len(cabecalho) + "\n")
        for nome, e in cenarios_estatisticas:
            if e is None:
                arquivo.write("%-20s sem amostras\n" % nome)
                continue
            arquivo.write(
                "%-20s %5d %7d %10.3f %10.3f %10.3f %10.3f %10.3f %12.2f [%8.3f, %8.3f]\n"
                % (
                    nome,
                    e["repeticoes"],
                    e["n"],
                    e["media"],
                    e["mediana"],
                    e["desvio_padrao"],
                    e["p95"],
                    e["p99"],
                    e["percentual_violacoes"],
                    e["ic_95_inferior"],
                    e["ic_95_superior"],
                )
            )
    print(open(caminho_saida).read())


def gerar_grafico_boxplot_comparativo(cenarios_dados, caminho_saida):
    nomes = [nome for nome, repeticoes in cenarios_dados if repeticoes]
    dados = [np.concatenate(repeticoes) for nome, repeticoes in cenarios_dados if repeticoes]

    plt.figure(figsize=(max(6, 2 * len(nomes)), 6))
    # Ticks definidos manualmente (em vez do parâmetro labels/tick_labels
    # do boxplot, cujo nome mudou entre versões do Matplotlib) para
    # manter compatibilidade tanto com Matplotlib < 3.9 quanto >= 3.9.
    caixa = plt.boxplot(dados, showmeans=True, patch_artist=True)
    cores = plt.cm.tab10(np.linspace(0, 1, len(nomes)))
    for patch, cor in zip(caixa["boxes"], cores):
        patch.set_facecolor(cor)
        patch.set_alpha(0.6)
    plt.axhline(y=LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")
    plt.ylabel("Latência one-way (ms)")
    plt.title("Comparação de latência uRLLC entre cenários (escala logarítmica)")
    plt.xticks(range(1, len(nomes) + 1), nomes, rotation=15)
    plt.legend()
    plt.grid(True, alpha=0.3, axis="y")
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def gerar_grafico_barras_comparativo(cenarios_estatisticas, caminho_saida):
    nomes = [nome for nome, e in cenarios_estatisticas if e is not None]
    medias = [e["media"] for nome, e in cenarios_estatisticas if e is not None]
    erros = [
        (e["media"] - e["ic_95_inferior"], e["ic_95_superior"] - e["media"])
        for nome, e in cenarios_estatisticas if e is not None
    ]
    erros_baixo = [0.0 if not np.isfinite(e[0]) else e[0] for e in erros]
    erros_alto = [0.0 if not np.isfinite(e[1]) else e[1] for e in erros]

    posicoes = np.arange(len(nomes))
    plt.figure(figsize=(max(6, 2 * len(nomes)), 6))
    plt.bar(posicoes, medias, yerr=[erros_baixo, erros_alto], capsize=5, color="tab:blue", alpha=0.75)
    plt.axhline(y=LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")
    plt.xticks(posicoes, nomes, rotation=15)
    plt.ylabel("Latência média (ms) com IC 95% — escala log")
    plt.title("Latência média por cenário (IC 95% entre repetições)")
    plt.legend()
    plt.grid(True, alpha=0.3, axis="y")
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=120)
    plt.close()


def gerar_grafico_cdf_comparativo(cenarios_dados, caminho_saida):
    """Gera uma ECDF única para comparar a distribuição dos cenários."""
    plt.figure(figsize=(10, 6))
    for nome, repeticoes in cenarios_dados:
        if not repeticoes:
            continue
        valores = np.sort(np.concatenate(repeticoes))
        fracao_acumulada = np.arange(1, len(valores) + 1) / len(valores)
        plt.step(valores, fracao_acumulada, where="post", linewidth=1.8, label=nome)
    plt.axvline(LIMIAR_LATENCIA_MS, color="red", linestyle="--", label="Limiar de 5 ms")
    plt.xscale("log")
    plt.xlabel("Latência one-way (ms, escala logarítmica)")
    plt.ylabel("Fração acumulada de amostras")
    plt.title("ECDF comparativa da latência uRLLC")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=160)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Compara latências uRLLC entre vários cenários de experimento.")
    parser.add_argument(
        "--cenario", action="append", required=True,
        help='Par "nome:caminho_csv", pode ser repetido para vários cenários.'
    )
    parser.add_argument("--saida", default="resultados/comparacao", help="Prefixo dos arquivos de saída")
    args = parser.parse_args()

    cenarios_dados = []
    for item in args.cenario:
        nome, caminhos = item.split(":", 1)
        repeticoes = [ler_latencias(caminho.strip()) for caminho in caminhos.split(",")]
        cenarios_dados.append((nome.strip(), repeticoes))

    cenarios_estatisticas = [(nome, calcular_estatisticas(valores)) for nome, valores in cenarios_dados]

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    escrever_tabela(cenarios_estatisticas, args.saida + "_tabela.txt")
    gerar_grafico_boxplot_comparativo(cenarios_dados, args.saida + "_boxplot.png")
    gerar_grafico_barras_comparativo(cenarios_estatisticas, args.saida + "_barras.png")
    gerar_grafico_cdf_comparativo(cenarios_dados, args.saida + "_cdf.png")
    print("Comparação salva com prefixo: %s" % args.saida)


if __name__ == "__main__":
    main()
