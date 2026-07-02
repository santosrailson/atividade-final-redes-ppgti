# Sistema de Monitoramento e Controle Closed Loop para Aplicações uRLLC em Rede 5G com Open vSwitch

Projeto final da disciplina Redes de Computadores do Mestrado em Tecnologia da Informação.

## Objetivo

Desenvolver um sistema de monitoramento e controle em malha fechada para garantir que aplicações do tipo uRLLC não excedam 5 ms de latência fim-a-fim na rede de transporte de uma operadora 5G, coexistindo com tráfego eMBB de alto volume.

## Ambiente técnico

Esta atividade foi desenvolvida e executada no seguinte ambiente:

| Item | Especificação |
|---|---|
| Sistema operacional | Debian GNU/Linux 13 (trixie) |
| Kernel | Linux 6.12.85+deb13-amd64 (SMP, PREEMPT_DYNAMIC) |
| Arquitetura | x86_64 |
| Python do sistema | 3.13.5 |
| Ambiente virtual | `/root/atividade-final-redes-ppgti/.venv` (Python 3.13.5) |
| Scapy | 2.7.0 |

> **Observação**: por ser um ambiente baseado em Debian 13 com Python 3.13, algumas dependências tradicionais do ecossistema Mininet/P4 podem exigir instalação manual ou ajustes de compatibilidade. Os scripts da atividade foram adaptados para rodar nesse ambiente.

## Tecnologias

- **Mininet**: emulação da topologia de rede.
- **Open vSwitch (OVS)**: switches virtuais com OpenFlow 1.3 e QoS/HTB.
- **Python + Scapy**: geração e monitoramento do tráfego uRLLC sobre TCP.
- **iperf3**: geração do tráfego eMBB.
- **Matplotlib / Pandas**: coleta e visualização de resultados.

## Estrutura do Repositório

```
├── docs/                           # Documentação didática
│   ├── 01_fundamentos_python.md
│   ├── 02_fundamentos_mininet.md
│   ├── 04_comentarios_etapa1.md
│   ├── 05_comentarios_etapa2.md
│   ├── 06_comentarios_etapa3.md
│   ├── 07_experimentos_baixa_latencia.md
│   ├── 08_analise_gargalo_versao_original.md
│   ├── 09_melhorias_versao_original.md
│   ├── 10_gerador_scapy_tcp.md
│   ├── 12_arquitetura_ovs_puro_scapy.md
│   └── resultados/                 # CSVs, eventos e graficos gerados pelos experimentos
├── etapa1_ambiente/                # Etapa 1: Mininet + Python
│   ├── instalar_dependencias.sh
│   ├── topologia_simples.py
│   ├── teste_ping.py
│   └── teste_latencia_scapy.py
└── etapa3_solucao/                 # Etapa 3: Closed Loop com OVS
    ├── topologia_ovs_puro_scapy.py
    ├── experimento_ovs_puro_scapy.py
    ├── gerador_urllc_scapy.py
    ├── monitor_controlador_scapy.py
    ├── gerador_urllc_scapy_otimizado.py
    ├── monitor_controlador_scapy_otimizado.py
    ├── gerador_urllc.py
    ├── monitor_controlador.py
    ├── gerador_embb.py
    └── coletar_resultados.py
```

## Instalação inicial

1. Clone ou acesse este repositório.
2. Execute o script de instalação das dependências básicas:
   ```bash
   bash etapa1_ambiente/instalar_dependencias.sh
   ```

> **Atenção**: o Mininet precisa de privilégios de root para criar namespaces de rede e interfaces virtuais. Por isso, os scripts de topo Mininet devem ser executados com `sudo`.

## Execução automática por etapa

### Etapa 1 — Mininet + Python
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/topologia_simples.py
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/teste_ping.py
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/teste_latencia_scapy.py
```

### Etapa 3 — Sistema Closed Loop com OVS puro
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

## Arquitetura OVS puro com Scapy/TCP

A solução final adota **4 switches OVS em linha** (`r1 -> r2 -> r3 -> r4`) com as seguintes características:

- Domínio L2 único (`10.0.0.0/16`) para simplificar o encaminhamento.
- QoS/HTB em cada porta OVS com duas filas:
  - **Fila 1**: alta prioridade para uRLLC (TCP porta 5000).
  - **Fila 0**: prioridade normal para eMBB/default.
- Regras OpenFlow 1.3 classificam o tráfego uRLLC e o direcionam para a fila de alta prioridade.
- Controle Closed Loop preventivo ou reativo, que dropa o tráfego eMBB quando a latência ultrapassa 5 ms.
- Gerador e monitor uRLLC usam `StreamSocket` do Scapy sobre TCP.

### Resultados (latência one-way)

| Cenário | Latência média | % > 5 ms |
|---|---|---|
| uRLLC isolado | **2,09 ms** | ~2,4% |
| uRLLC + eMBB 5M UDP (preventivo) | **2,05 ms** | ~4,5% |
| uRLLC + eMBB 10M UDP (reativo) | **1,97 ms** | ~3,1% |

Percentis representativos (eMBB 5M UDP preventivo, 60 s):

| Percentil | Latência one-way |
|---|---|
| p50 | 1,45 ms |
| p75 | 2,09 ms |
| p90 | 3,50 ms |
| p95 | 4,53 ms |
| p99 | 11,01 ms |

Os gráficos, CSVs de latência e arquivo de eventos são salvos em `docs/resultados/`.

Veja detalhes em `docs/12_arquitetura_ovs_puro_scapy.md`.

## Como funciona o controle Closed Loop

1. O **monitor** escuta na porta TCP 5000 e recebe pacotes uRLLC do gerador.
2. Para cada pacote, calcula a latência one-way (timestamp de chegada − timestamp de envio).
3. Se duas medições consecutivas ultrapassarem 5 ms, envia um sinal para ativar o controle.
4. O orquestrador recebe o sinal e instala regras OpenFlow nos switches OVS para descartar o tráfego eMBB (UDP porta 5001).
5. Quando a latência normaliza, o controle é desativado e o eMBB volta a fluir.

## Por que não P4?

Embora P4/BMv2 ofereça programabilidade do plano de dados, o **BMv2 é um switch de software de referência** sem otimização de desempenho. Nos testes realizados, a combinação BMv2 + Scapy/TCP não conseguiu manter a latência uRLLC consistentemente abaixo de 5 ms. Por isso, a implementação final adotou **Open vSwitch**, que possui datapath otimizado e atendeu ao requisito de latência.
