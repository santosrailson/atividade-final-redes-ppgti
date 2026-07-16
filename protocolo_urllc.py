#!/usr/bin/env python3
"""Enquadramento das mensagens uRLLC transportadas em um fluxo TCP.

TCP não preserva fronteiras de mensagens. Cada registro possui tamanho fixo
e inclui identificador, timestamp e sequência, permitindo remontar leituras
fragmentadas/agregadas e auditar perdas sem confundir bytes com pacotes.
"""

import struct

FORMATO = "!4sId"
MAGIC = b"URLC"
TAMANHO_MENSAGEM = struct.calcsize(FORMATO)


def codificar_mensagem(sequencia, timestamp):
    return struct.pack(FORMATO, MAGIC, int(sequencia), float(timestamp))


def decodificar_mensagem(dados):
    if len(dados) != TAMANHO_MENSAGEM:
        raise ValueError("mensagem uRLLC com tamanho inválido")
    magic, sequencia, timestamp = struct.unpack(FORMATO, dados)
    if magic != MAGIC:
        raise ValueError("assinatura uRLLC inválida")
    return sequencia, timestamp


def extrair_mensagens(buffer):
    """Retorna (mensagens, sobra), preservando registros incompletos."""
    mensagens = []
    while len(buffer) >= TAMANHO_MENSAGEM:
        bloco, buffer = buffer[:TAMANHO_MENSAGEM], buffer[TAMANHO_MENSAGEM:]
        mensagens.append(decodificar_mensagem(bloco))
    return mensagens, buffer
