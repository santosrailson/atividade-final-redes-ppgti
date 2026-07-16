#!/bin/bash
# Executa cenários independentes com repetições e preserva todas as evidências.
set -euo pipefail

DIRETORIO_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIRETORIO_SCRIPT"

DURACAO=${DURACAO:-60}
TAXA_EMBB=${TAXA_EMBB:-12M}
REPETICOES=${REPETICOES:-5}
RESULTADOS="$DIRETORIO_SCRIPT/resultados"
EXECUCOES="$RESULTADOS/execucoes"
mkdir -p "$EXECUCOES"

executar_cenario() {
    local nome="$1"
    shift
    local consolidado="$RESULTADOS/latencias_${nome}.csv"
    rm -f "$consolidado"

    for repeticao in $(seq 1 "$REPETICOES"); do
        local pasta="$EXECUCOES/$nome/rep_$(printf '%02d' "$repeticao")"
        rm -rf "$pasta"
        mkdir -p "$pasta"
        printf '\n=== Cenário %s | repetição %d/%d ===\n' "$nome" "$repeticao" "$REPETICOES"
        python3 experimento.py --duracao "$DURACAO" --taxa-embb "$TAXA_EMBB" \
            --diretorio-saida "$pasta" "$@" | tee "$pasta/execucao.log"

        if [ "$repeticao" -eq 1 ]; then
            cp "$pasta/latencias_urllc.csv" "$consolidado"
        else
            tail -n +2 "$pasta/latencias_urllc.csv" >> "$consolidado"
        fi
    done
}

cat > "$RESULTADOS/manifesto_experimento.txt" <<EOF
data_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
duracao_segundos=$DURACAO
taxa_embb_por_fluxo=$TAXA_EMBB
repeticoes=$REPETICOES
python=$(python3 --version 2>&1)
kernel=$(uname -a)
EOF

executar_cenario isolado     --sem-embb --controle nenhum --qos-estatico
executar_cenario sem_qos     --controle nenhum --no-qos-estatico
executar_cenario qos_estatico --controle nenhum --qos-estatico
executar_cenario reativo     --controle reativo --qos-estatico

lista_csv() { local IFS=,; echo "$*"; }

python3 comparar_cenarios.py \
    --cenario "Isolado:$(lista_csv "$EXECUCOES"/isolado/rep_*/latencias_urllc.csv)" \
    --cenario "Sem QoS:$(lista_csv "$EXECUCOES"/sem_qos/rep_*/latencias_urllc.csv)" \
    --cenario "QoS estático:$(lista_csv "$EXECUCOES"/qos_estatico/rep_*/latencias_urllc.csv)" \
    --cenario "Closed loop:$(lista_csv "$EXECUCOES"/reativo/rep_*/latencias_urllc.csv)" \
    --saida "$RESULTADOS/comparacao"

echo "Bateria concluída. Evidências preservadas em $RESULTADOS"
