#!/bin/bash

set -e

RAIZ="/opt/ferramentas_p4"
mkdir -p "${RAIZ}"
cd "${RAIZ}"

apt-get update
apt-get install -y git curl wget build-essential

if [ ! -d p4-guide ]; then
    git clone https://github.com/jafingerhut/p4-guide.git
fi

cd p4-guide/bin
chmod +x install-p4dev-v7.sh
./install-p4dev-v7.sh 2>&1 | tee "${RAIZ}/instalacao_p4.log"
