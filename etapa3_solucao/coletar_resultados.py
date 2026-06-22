#!/usr/bin/env python3

import os
import sys


def ler_latencias(caminho_csv):
    valores = []
    if not os.path.exists(caminho_csv):
        return valores

    with open(caminho_csv, "r") as arquivo:
        linhas = arquivo.readlines()[1:]
        for linha in linhas:
            linha = linha.strip()
            if linha:
                valores.append(float(linha))
    return valores


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
    if not valores:
        return 0, 0, 0, 0, 0

    quantidade = len(valores)
    media = sum(valores) / quantidade
    minimo = min(valores)
    maximo = max(valores)
    violacoes = sum(1 for v in valores if v > 5.0)
    return quantidade, media, minimo, maximo, violacoes


def gerar_grafico(latencias, caminho_saida, caminho_eventos="/tmp/eventos_controle.txt"):
    import matplotlib.pyplot as plt

    if not latencias:
        print("Nenhuma latencia para plotar.")
        return

    eventos = ler_eventos(caminho_eventos)
    tempo_inicial = eventos[0][0] if eventos else 0

    plt.figure(figsize=(12, 6))
    plt.plot(latencias, marker="o", linestyle="-", color="blue", label="Latencia uRLLC")
    plt.axhline(y=5.0, color="red", linestyle="--", label="Limiar de 5 ms")

    for timestamp, evento in eventos:
        if evento == "controle_ativar":
            indice = int(timestamp - tempo_inicial)
            if 0 <= indice < len(latencias):
                plt.axvline(x=indice, color="green", linestyle=":", alpha=0.7, label="Controle ativado")
        elif evento == "controle_desativar":
            indice = int(timestamp - tempo_inicial)
            if 0 <= indice < len(latencias):
                plt.axvline(x=indice, color="orange", linestyle=":", alpha=0.7, label="Controle desativado")

    plt.xlabel("Amostra")
    plt.ylabel("Latencia (ms)")
    plt.title("Latencia uRLLC ao longo do tempo")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(caminho_saida)
    print("Grafico salvo em %s" % caminho_saida)


def main():
    caminho_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/latencias_urllc.csv"
    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else "/tmp/grafico_latencias.png"
    caminho_eventos = sys.argv[3] if len(sys.argv) > 3 else "/tmp/eventos_controle.txt"

    latencias = ler_latencias(caminho_csv)
    quantidade, media, minimo, maximo, violacoes = calcular_estatisticas(latencias)

    print("=== Resultados do experimento ===")
    print("Amostras coletadas: %d" % quantidade)
    print("Latencia media: %.3f ms" % media)
    print("Latencia minima: %.3f ms" % minimo)
    print("Latencia maxima: %.3f ms" % maximo)
    print("Violacoes acima de 5 ms: %d" % violacoes)

    gerar_grafico(latencias, caminho_saida, caminho_eventos)


if __name__ == "__main__":
    main()
