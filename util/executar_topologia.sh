#!/bin/bash

set -e

RAIZ_PROJETO="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${RAIZ_PROJETO}/mininet:${PYTHONPATH}"

python3 "${RAIZ_PROJETO}/mininet/topologia.py" --cli "$@"
