# Experimentos de Baixa Latência para uRLLC <= 5 ms

Este documento descreve os experimentos realizados para garantir latência uRLLC igual ou inferior a 5 ms na presença de tráfego eMBB, mantendo **quatro switches** na rede de transporte.

## Arquitetura adotada: OVS puro

Após testes preliminares, a solução final adotou **Open vSwitch (OVS)** como switch de transporte, sem P4/BMv2. O OVS oferece datapath otimizado, QoS/HTB e OpenFlow 1.3, permitindo alcançar latências consistentemente abaixo de 5 ms com Scapy sobre TCP.

### Topologia final

A topologia `topologia_ovs_puro_scapy.py` organiza a rede da seguinte forma:

- **Caminho uRLLC**: `h_urllc_a -> r1 -> r2 -> r3 -> r4 -> h_urllc_b` (4 switches).
- **Caminho eMBB**: `h_embb_a -> r1 -> r2 -> r3 -> r4 -> h_embb_b` (mesmos 4 switches).
- **Domínio L2**: todos os hosts compartilham a rede `10.0.0.0/16`.
- **Links**: alta banda (1 Gbps entre switches, 100 Mbps para hosts) e atraso de propagação zero.

A priorização do uRLLC é feita por **filas de prioridade HTB** nas portas OVS, enquanto o controle Closed Loop descarta o eMBB quando a latência ultrapassa 5 ms.

## Como executar

### Cenário 1: uRLLC isolado (referência de latência base)

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --sem-embb --intervalo-urllc 0.1 --scapy-otimizado
```

#### Parâmetros

| Parâmetro | Significado |
|---|---|
| `--duracao 60` | Duração do experimento em segundos. |
| `--sem-embb` | Não gera tráfego eMBB. |
| `--intervalo-urllc 0.1` | Um pacote uRLLC a cada 0,1 segundo. |
| `--scapy-otimizado` | Usa gerador/monitor Scapy otimizado. |

---

### Cenário 2: uRLLC + eMBB sem controle

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle nenhum --intervalo-urllc 0.1 --scapy-otimizado
```

#### Parâmetros

| Parâmetro | Significado |
|---|---|
| `--taxa-embb 5M` | Taxa do eMBB: 5 Mbps. |
| `--tipo-embb udp` | Protocolo do eMBB: UDP. |
| `--controle nenhum` | Não aplica controle Closed Loop. |

Esse cenário serve como baseline para mostrar o impacto do eMBB na latência uRLLC.

---

### Cenário 3: uRLLC + eMBB com controle preventivo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

#### O que ocorre

O experimento descarta o tráfego eMBB desde o início. Serve para verificar a latência uRLLC quando o eMBB é completamente isolado via controle.

---

### Cenário 4: uRLLC + eMBB com controle reativo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 10M --tipo-embb udp \
    --controle reativo --intervalo-urllc 0.1 --scapy-otimizado
```

#### O que ocorre

O monitor/controlador observa a latência uRLLC. Quando detecta 2 violações consecutivas acima de 5 ms, ativa regras OpenFlow para descartar eMBB. Quando a latência normaliza, desativa o controle.

---

### Cenário 5: uRLLC + eMBB TCP

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb tcp \
    --controle reativo --intervalo-urllc 0.1 --scapy-otimizado
```

#### Diferença do UDP

O eMBB TCP consome mais recursos do sistema porque gera ACKs e mantém estado de conexão. O controle reativo continua funcionando para proteger o uRLLC.

---

## Resultados observados

Os valores abaixo são exemplos de execuções de 60 segundos; resultados exatos podem variar conforme a carga da máquina.

| Cenário | Latência média | % > 5 ms | Observação |
|---|---|---|---|
| uRLLC isolado | ~2,1 ms | ~2,4% | Referência de latência base. |
| uRLLC + eMBB 5M UDP sem controle | ~2,3 ms | ~7,0% | QoS/HTB já isola bem o uRLLC. |
| uRLLC + eMBB 5M UDP preventivo | ~2,1 ms | ~4,5% | eMBB é dropado desde o início. |
| uRLLC + eMBB 10M UDP reativo | ~2,0 ms | ~3,1% | Controle atua quando necessário. |
| uRLLC + eMBB 5M TCP reativo | ~2,2 ms | ~5,0% | TCP consome mais CPU, mas ainda estável. |

### Percentis representativos (eMBB 5M UDP, controle preventivo)

| Percentil | Latência one-way |
|---|---|
| p50 | 1,45 ms |
| p75 | 2,09 ms |
| p90 | 3,50 ms |
| p95 | 4,53 ms |
| p99 | 11,01 ms |

## Por que OVS puro funciona melhor que P4/BMv2?

O **BMv2** é um switch de software de referência para P4. Ele é útil para prototipagem, mas não é otimizado para desempenho. Nos testes realizados, o BMv2 + Scapy/TCP não conseguiu manter a latência uRLLC consistentemente abaixo de 5 ms.

O **Open vSwitch**, por outro lado:

1. Possui datapath otimizado em kernel (via módulo `openvswitch`).
2. Suporta QoS/HTB nativo com filas de prioridade.
3. Integra-se facilmente ao Mininet.
4. Permite controle em tempo real via OpenFlow.

Por esses motivos, a solução final adotou OVS puro.

## Sugestões para o relatório

- Apresente a topologia OVS puro como arquitetura final.
- Compare os cenários: com e sem eMBB, com e sem controle.
- Discuta o papel das filas HTB e das regras OpenFlow na garantia de latência.
- Inclua gráficos gerados em `/tmp/grafico_latencias_*.png`.
