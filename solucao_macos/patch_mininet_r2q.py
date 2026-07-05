#!/usr/bin/env python3
"""
Corrige na origem o aviso benigno do kernel:

    sch_htb: quantum of class X is big. Consider r2q change.

O Mininet cria a fila HTB usada para limitar a banda de cada link
(parametro bw= em addLink) com o r2q padrao do tc (10), em
mininet/link.py (classe TCIntf, metodo config). O quantum de uma
classe HTB e calculado como taxa_em_bytes/r2q quando nenhum "quantum"
explicito e informado; com r2q=10 e as taxas usadas neste projeto
(100 Mbit nos links de acesso, 1000 Mbit no tronco), o quantum
calculado ultrapassa o teto interno do kernel (~60000 bytes) e gera o
aviso -- que nao afeta o funcionamento (a fila continua limitando a
taxa corretamente), so avisa que o quantum ficou maior que o ideal.

Como o aviso e impresso no exato momento em que a classe HTB e criada
(dentro de rede.start(), antes de qualquer codigo nosso rodar),
corrigir isso depois de pronto (ex.: com `tc class change`) nao
apaga o aviso ja emitido -- e preciso que o Mininet ja crie a classe
com um r2q maior. Este script faz um unico ajuste textual no arquivo
instalado do Mininet, aumentando o r2q usado nessa fila (a mesma
correcao que o proprio kernel sugere na mensagem: "Consider r2q
change").

Rodado uma unica vez durante o build da imagem Docker (ver
Dockerfile) -- nao e executado em tempo de experimento.
"""
import sys

CAMINHO = "/usr/lib/python3/dist-packages/mininet/link.py"
ANTIGO = "root handle 5:0 htb default 1',"
NOVO = "root handle 5:0 htb default 1 r2q 4000',"

with open(CAMINHO, "r") as arquivo:
    conteudo = arquivo.read()

ocorrencias = conteudo.count(ANTIGO)
if ocorrencias != 1:
    sys.exit(
        "Esperava exatamente 1 ocorrencia do padrao HTB em %s, encontrei %d. "
        "A versao do Mininet instalada pode ter mudado o codigo-fonte -- "
        "ajuste o texto ANTIGO/NOVO deste script antes de prosseguir."
        % (CAMINHO, ocorrencias)
    )

conteudo = conteudo.replace(ANTIGO, NOVO)
with open(CAMINHO, "w") as arquivo:
    arquivo.write(conteudo)

print("mininet/link.py corrigido: r2q do HTB de banda aumentado para 4000.")
