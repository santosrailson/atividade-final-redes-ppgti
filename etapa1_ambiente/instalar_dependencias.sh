#!/bin/bash

atualizar_repositorios() {
    sudo apt-get update
}

instalar_mininet() {
    sudo apt-get install -y mininet
    sudo apt-get install -y openvswitch-switch
    sudo apt-get install -y openvswitch-testcontroller
    sudo ln -sf /usr/bin/ovs-testcontroller /usr/bin/ovs-controller
}

instalar_ferramentas_trafego() {
    sudo apt-get install -y iperf3
    sudo apt-get install -y ffmpeg
}

instalar_python_e_venv() {
    sudo apt-get install -y python3
    sudo apt-get install -y python3-venv
    sudo apt-get install -y python3-pip
}

criar_ambiente_virtual() {
    if [ -d ".venv" ]; then
        rm -rf .venv
    fi
    python3 -m venv .venv --system-site-packages
}

instalar_bibliotecas_python() {
    source .venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip install scapy
    python3 -m pip install matplotlib
    python3 -m pip install pandas
}

verificar_instalacao() {
    source .venv/bin/activate
    python3 - <<'PYTHON'
import mininet
import scapy
import matplotlib
import pandas

print("Mininet: OK")
print("Scapy: OK")
print("Matplotlib: OK")
print("Pandas: OK")
PYTHON
    mn --test pingall
}

atualizar_repositorios
instalar_python_e_venv
instalar_mininet
instalar_ferramentas_trafego
criar_ambiente_virtual
instalar_bibliotecas_python
verificar_instalacao
