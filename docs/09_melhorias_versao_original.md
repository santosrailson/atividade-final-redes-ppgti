# Melhorias na solução OVS puro

Este documento descreve as melhorias testadas na solução final com **Open vSwitch (OVS) puro**, objetivando manter a latência uRLLC igual ou inferior a 5 ms na maioria dos casos.

## Melhorias testadas

1. **Otimização do gerador/monitor Scapy**: uso de `StreamSocket` sobre socket TCP real, com `TCP_NODELAY`, `TCP_QUICKACK`, `SO_PRIORITY` e prioridade de processo.
2. **QoS/HTB com filas de prioridade**: configuração de duas filas por porta OVS, onde uRLLC (TCP porta 5000) usa a fila 1 de alta prioridade.
3. **Regras OpenFlow de classificação**: prioridade alta para tráfego uRLLC e regras de drop para eMBB quando o controle é ativado.
4. **Controle Closed Loop preventivo e reativo**: descarte de eMBB desde o início ou ativado por violações de latência.
5. **Domínio L2 único**: eliminação do roteamento L3, reduzindo o processamento nos switches.

## Script de teste

Os experimentos são executados com o orquestrador:

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle reativo --intervalo-urllc 0.1 --scapy-otimizado
```

### Parâmetros do comando

| Parâmetro | Significado |
|---|---|
| `--duracao 60` | Duração do experimento em segundos. |
| `--taxa-embb 5M` | Taxa do tráfego eMBB: 5 Mbps. |
| `--tipo-embb udp` | Protocolo do eMBB: UDP. |
| `--controle reativo` | Ativa o controle apenas quando a latência violar 5 ms. |
| `--intervalo-urllc 0.1` | Intervalo entre pacotes uRLLC em segundos. |
| `--scapy-otimizado` | Usa gerador/monitor Scapy otimizado. |

## Resultados

### Topologia OVS puro com 4 switches em linha

| Cenário | Latência média | % > 5 ms | Observação |
|---|---|---|---|
| uRLLC isolado | 2,09 ms | ~2,4% | Referência de latência base. |
| uRLLC + eMBB 5M UDP (sem controle) | 2,30 ms | ~7,0% | Filas HTB já isolam bem. |
| uRLLC + eMBB 5M UDP (preventivo) | 2,05 ms | ~4,5% | eMBB dropado desde o início. |
| uRLLC + eMBB 10M UDP (reativo) | 1,97 ms | ~3,1% | Controle atua quando necessário. |
| uRLLC + eMBB 5M TCP (reativo) | 2,20 ms | ~5,0% | TCP consome mais CPU, mas estável. |

### Percentis representativos (eMBB 5M UDP, controle preventivo)

| Percentil | Latência one-way |
|---|---|
| p50 | 1,45 ms |
| p75 | 2,09 ms |
| p90 | 3,50 ms |
| p95 | 4,53 ms |
| p99 | 11,01 ms |

## Análise

### 1. Otimização do Scapy

A versão otimizada (`gerador_urllc_scapy_otimizado.py` e `monitor_controlador_scapy_otimizado.py`) reduziu significativamente o overhead do Scapy ao usar `StreamSocket` sobre socket TCP real. Isso elimina a necessidade de o Scapy construir e enviar pacotes raw a cada iteração, reduzindo a latência em aproximadamente 50% em comparação com a versão não otimizada.

### 2. QoS/HTB com filas de prioridade

A configuração de duas filas HTB por porta OVS garante que o tráfego uRLLC seja encaminhado antes do eMBB mesmo quando ambos competem pelo mesmo link. A fila 1 tem `min-rate` alto (500 Mbps) e `max-rate` de 1 Gbps, enquanto a fila 0 tem `min-rate` baixo (1 Mbps).

### 3. Regras OpenFlow

As regras OpenFlow classificam o tráfego por porta:

```bash
# uRLLC -> fila 1
ovs-ofctl add-flow r1 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'
ovs-ofctl add-flow r1 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'

# eMBB/default -> fila 0
ovs-ofctl add-flow r1 'priority=10,actions=set_queue:0,normal'
```

Quando o controle é ativado, uma regra de maior prioridade descarta o eMBB:

```bash
ovs-ofctl add-flow r1 'priority=200,udp,tp_dst=5001,actions=drop'
```

### 4. Controle Closed Loop

O monitor/controlador mede a latência one-way de cada pacote uRLLC. Se a latência ultrapassar 5 ms por 2 amostras consecutivas, o atuador instala regras de drop de eMBB. Quando a latência normaliza, as regras são removidas.

### 5. Domínio L2 único

A eliminação do roteamento L3 reduz o processamento nos switches. Como todos os hosts compartilham a rede `10.0.0.0/16`, o OVS pode encaminhar pacotes usando o modo `normal` (learning switch), que é altamente otimizado.

## Conclusão

A combinação de **OVS puro + Scapy otimizado + QoS/HTB + OpenFlow + controle Closed Loop** conseguiu manter a latência uRLLC consistentemente abaixo de 5 ms na maioria dos cenários, mesmo com eMBB compartilhando os mesmos 4 switches.

| Abordagem | Consegue <= 5 ms na maioria? | Viável dentro do enunciado? |
|---|---|---|
| OVS puro + Scapy otimizado + QoS | **Sim** | **Sim** |
| OVS puro + controle preventivo | **Sim** | **Sim** |
| OVS puro + controle reativo | **Sim** | **Sim** |

## Recomendação

Para o relatório final, recomenda-se apresentar:

1. A **arquitetura OVS pura** como solução final.
2. O **experimento com controle preventivo** como cenário principal de entrega.
3. O **experimento com controle reativo** como demonstração do closed loop funcionando.
4. O **cenário sem eMBB** como baseline.

O comando principal de entrega pode ser:

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

Esse comando mantém 4 switches, uRLLC Scapy/TCP, eMBB com iperf, e atinge latência média ~2 ms com a maioria das amostras abaixo de 5 ms.
