#!/bin/bash
# Bateria de testes padrão para o artigo: roda 4 cenários em sequência
#
#   1. uRLLC isolado (sem eMBB concorrente)          -> baseline
#   2. uRLLC + eMBB, SEM controle closed loop        -> mostra o problema
#   3. uRLLC + eMBB, controle PREVENTIVO             -> eMBB já limitado desde o início
#   4. uRLLC + eMBB, controle REATIVO                -> só limita ao violar 5 ms
#
# e ao final gera a comparação estatística entre eles (tabela +
# boxplot + gráfico de barras com IC 95%).
#
# Deve ser executado DENTRO do container (o Mininet precisa criar
# namespaces de rede, o que exige o container --privileged):
#
#   docker compose run --rm urllc-lab ./executar_bateria_testes.sh
#
# Variáveis de ambiente opcionais:
#   DURACAO=90 TAXA_EMBB=10M ./executar_bateria_testes.sh
set -e

DIRETORIO_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIRETORIO_SCRIPT"

DURACAO=${DURACAO:-60}
TAXA_EMBB=${TAXA_EMBB:-5M}
RESULTADOS="$DIRETORIO_SCRIPT/resultados"
mkdir -p "$RESULTADOS"

executar_cenario() {
    local nome="$1"
    shift
    echo ""
    echo "=============================================="
    echo "  Cenário: $nome"
    echo "=============================================="
    python3 experimento.py --duracao "$DURACAO" "$@"
    # Cada cenário sobrescreve resultados/latencias_urllc.csv; guardamos
    # uma cópia com nome próprio antes de rodar o cenário seguinte.
    cp "$RESULTADOS/latencias_urllc.csv" "$RESULTADOS/latencias_${nome}.csv"
}

executar_cenario isolado          --sem-embb
executar_cenario sem_controle     --controle nenhum     --taxa-embb "$TAXA_EMBB"
executar_cenario preventivo       --controle preventivo --taxa-embb "$TAXA_EMBB"
executar_cenario reativo          --controle reativo    --taxa-embb "$TAXA_EMBB"

echo ""
echo "=============================================="
echo "  Comparando os 4 cenários"
echo "=============================================="
python3 comparar_cenarios.py \
    --cenario "Isolado:$RESULTADOS/latencias_isolado.csv" \
    --cenario "Sem controle:$RESULTADOS/latencias_sem_controle.csv" \
    --cenario "Preventivo:$RESULTADOS/latencias_preventivo.csv" \
    --cenario "Reativo:$RESULTADOS/latencias_reativo.csv" \
    --saida "$RESULTADOS/comparacao"

echo ""
echo "Bateria de testes concluída. Veja os arquivos em $RESULTADOS/"
