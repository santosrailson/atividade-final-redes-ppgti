#!/bin/bash

set -e

NUM_JOBS=$(nproc)
RAIZ="/opt/ferramentas_p4"
mkdir -p "${RAIZ}"
cd "${RAIZ}"

instalar_p4c() {
    echo "=== Instalando p4c ==="
    if [ ! -d p4c ]; then
        git clone --recursive https://github.com/p4lang/p4c.git
    fi
    cd p4c
    git checkout main
    git pull
    git submodule update --init --recursive
    mkdir -p build
cd build
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local
    make -j"${NUM_JOBS}"
    make install
    ldconfig
    cd "${RAIZ}"
}

instalar_bmv2() {
    echo "=== Instalando behavioral-model ==="
    if [ ! -d behavioral-model ]; then
        git clone https://github.com/p4lang/behavioral-model.git
    fi
    cd behavioral-model
    git checkout main
    git pull
    ./autogen.sh
    ./configure --with-thrift --with-pi --without-nanomsg
    make -j"${NUM_JOBS}"
    make install
    ldconfig
    cd "${RAIZ}"
}

instalar_p4_mininet() {
    echo "=== Instalando p4_mininet ==="
    if [ ! -d p4_mininet ]; then
        git clone https://github.com/p4lang/tutorials.git p4_tutorials
    fi
    cp p4_tutorials/utils/p4_mininet.py /usr/local/lib/python3.*/dist-packages/ 2>/dev/null || cp p4_tutorials/utils/p4_mininet.py /usr/lib/python3/dist-packages/
}

instalar_p4c
instalar_bmv2
instalar_p4_mininet

echo "=== Instalacao concluida ==="
