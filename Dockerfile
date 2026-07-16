# Imagem Linux com Mininet + Open vSwitch + Python/Scapy.
#
# O macOS (kernel Darwin) não possui namespaces de rede nem o
# datapath do Open vSwitch, então o Mininet não roda nativamente
# no host. Este Dockerfile cria um container Linux (Ubuntu 22.04)
# que roda dentro da VM Linux do Docker Desktop for Mac, permitindo
# emular a topologia de 4 switches OVS normalmente.
#
# O OVS aqui é configurado para usar o datapath em "userspace"
# (netdev), que não exige o módulo de kernel openvswitch.ko no
# host. Isso é essencial no Docker Desktop for Mac, pois a VM
# Linux interna normalmente não carrega esse módulo.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
# Garante que Python/bash consigam imprimir acentos (á, é, ç, ã...)
# corretamente mesmo se o container nao definir um locale UTF-8 por padrao.
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        mininet \
        openvswitch-switch \
        openvswitch-common \
        iproute2 \
        iperf3 \
        ethtool \
        net-tools \
        iputils-ping \
        tcpdump \
        python3 \
        python3-pip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Corrige na origem o aviso benigno do kernel "sch_htb: quantum of
# class X is big. Consider r2q change." causado pelo r2q padrao (10)
# que o Mininet usa ao criar a fila HTB de banda (bw= em addLink) --
# ver patch_mininet_r2q.py para a explicacao completa.
COPY patch_mininet_r2q.py /tmp/patch_mininet_r2q.py
RUN python3 /tmp/patch_mininet_r2q.py && rm /tmp/patch_mininet_r2q.py

# Corrige "*** Error setting resource limits. Mininet's performance
# may be affected." -- isola cada um dos 12 ajustes de kernel feitos
# por fixLimits() em seu proprio try/except, em vez de um unico bloco
# que aborta tudo no primeiro item que falhar (o que sempre acontece
# na VM do Docker Desktop for Mac) -- ver patch_mininet_fixlimits.py.
COPY patch_mininet_fixlimits.py /tmp/patch_mininet_fixlimits.py
RUN python3 /tmp/patch_mininet_fixlimits.py && rm /tmp/patch_mininet_fixlimits.py

# Bibliotecas Python usadas pelos scripts de geração/monitoramento
# (Scapy) e pela análise estatística dos resultados (pandas, numpy,
# scipy, matplotlib).
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

WORKDIR /app
COPY . /app

RUN chmod +x /app/entrypoint.sh /app/executar_bateria_testes.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["bash"]
