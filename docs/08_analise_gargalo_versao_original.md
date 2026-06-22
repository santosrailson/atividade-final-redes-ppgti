# Análise de gargalo da versão original (Scapy/TCP, 4 roteadores)

Este documento detalha a análise de desempenho da implementação que segue fielmente o enunciado da atividade: gerador uRLLC em Python com socket TCP (conforme o código original `gerador_urllc.py`), programa P4 original (`programa_qos.p4`) e topologia com **4 roteadores em linha** (`topologia_rede_transporte.py`).

## Cenários testados

Foram executados quatro cenários controlados para decompor a latência em seus componentes:

| Cenário | Topologia | Delay links | eMBB | Objetivo |
|---|---|---|---|---|
| A | 4R em linha | 2 ms | sem | Medir baseline com delay realista. |
| B | 4R em linha | 2 ms | 3M UDP | Medir impacto do eMBB. |
| C | 4R em linha | 0 ms | sem | Isolar overhead do BMv2/software. |
| D | 4R em linha | 0 ms | 3M UDP | Isolar impacto do eMBB sem delay. |
| E | 4R caminho curto | 0 ms | sem | Isolar impacto do número de saltos. |
| F | 4R caminho curto | 0 ms | 3M UDP | Caminho curto com eMBB separado. |

> **Nota:** em todos os cenários o gerador mede **RTT** (ida + volta). O monitor/receptor mede **one-way** (apenas ida).

## Resultados

### 4 roteadores em linha, delay 2 ms (configuração original)

| Métrica | uRLLC isolado | uRLLC + eMBB 3M |
|---|---|---|
| RTT mínimo | 16,29 ms | 15,92 ms |
| RTT média | 21,38 ms | 42,87 ms |
| RTT p95 | 33,28 ms | 55,32 ms |
| One-way mínima | 8,26 ms | 7,68 ms |
| One-way média | 11,17 ms | 23,04 ms |
| One-way p95 | 18,26 ms | 38,51 ms |
| Amostras > 5 ms | 100% | 100% |

**Interpretação:** mesmo sem eMBB, a latência one-way média é **11 ms**, mais que o dobro do limiar de 5 ms. O RTT mínimo fica em torno de **16 ms**, valor próximo ao atraso de propagação teórico de 16 ms (4 links × 2 ms × 2 sentidos).

### 4 roteadores em linha, delay 0 ms (isolar overhead do BMv2)

| Métrica | uRLLC isolado | uRLLC + eMBB 3M |
|---|---|---|
| RTT mínimo | 3,33 ms | 3,29 ms |
| RTT média | 7,91 ms | 18,39 ms |
| RTT p95 | 16,83 ms | 43,21 ms |
| One-way mínima | 1,81 ms | 1,43 ms |
| One-way média | 4,68 ms | 8,77 ms |
| One-way p95 | 9,00 ms | 20,28 ms |
| Amostras > 5 ms (RTT) | 72% | 78% |
| Amostras > 5 ms (one-way) | 31% | 39% |

**Interpretação:** ao zerar o delay dos links, a latência one-way média cai para **4,68 ms** sem eMBB — muito próximo do limiar. Isso mostra que o **atraso de propagação dos links é o maior componente** da latência na configuração original.

### 4 roteadores com caminho uRLLC curto, delay 0 ms

| Métrica | uRLLC isolado | uRLLC + eMBB 3M (caminho separado) |
|---|---|---|
| RTT mínimo | ~0,97 ms | ~0,97 ms |
| RTT média | ~3,54 ms | ~3,54 ms |
| RTT p95 | ~8,92 ms | ~8,92 ms |
| Amostras > 5 ms | ~15% | ~15% |

**Interpretação:** reduzindo o caminho uRLLC para 2 saltos e mantendo links de alta capacidade/baixo atraso, a maioria das amostras fica abaixo de 5 ms. Isso confirma que o **número de saltos** também é um gargalo importante no BMv2 em software.

## Decomposição do gargalo

A latência total no cenário original (4R em linha, 2 ms, eMBB 3M) pode ser decomposta aproximadamente em:

| Componente | Contribuição estimada (RTT) | Observação |
|---|---|---|
| Atraso de propagação dos links | ~16 ms | 4 saltos × 2 ms × 2 sentidos. |
| Processamento dos 4 switches P4 (BMv2 software) | ~3–5 ms | Medido pela diferença entre delay 0 ms e o mínimo teórico. |
| Competição com eMBB | ~15–20 ms | Diferença entre cenários com e sem eMBB. |
| Variabilidade do escalonador SO | picos > 1 s | Causa outliers extremos. |

### 1. Atraso de propagação dos links

Com delay=2 ms por link e 4 saltos no caminho uRLLC, o atraso de ida é 8 ms e o RTT é 16 ms. Esse é um **atraso físico incompressível** na topologia emulada. A única forma de reduzi-lo sem mudar a topologia é diminuir o parâmetro `delay` dos links.

### 2. Overhead de processamento P4/BMv2

Mesmo com delay=0 ms e sem eMBB, o RTT médio foi 7,91 ms para 4 saltos. Isso significa que o BMv2 em software adiciona aproximadamente **1 ms por salto** em média, além de variabilidade. O programa P4 original realiza:

- Parser de Ethernet + IPv4 + lookahead de TCP/UDP.
- Duas consultas de tabela (`tabela_classificacao`, `tabela_ipv4_lpm`).
- Decremento de TTL.
- Recálculo de checksum IPv4.
- Verificação de controle QoS.

Em hardware P4 real, cada uma dessas operações levaria microssegundos. No BMv2 em software, elas competem por CPU com os processos do host.

### 3. Competição com eMBB

Com eMBB 3M UDP ativo, a latência RTT média salta de 21,38 ms para 42,87 ms no cenário com delay=2 ms, e de 7,91 ms para 18,39 ms no cenário com delay=0 ms. O eMBB compete por:

- **CPU do host:** processos do iperf e do BMv2 dividem os mesmos cores.
- **Banda dos links:** os links r1-r2, r2-r3, r3-r4 têm `bw=10 Mbps`; o eMBB 3M ocupa parte dessa banda.
- **Filas do traffic manager:** sem `--priority-queues`, o BMv2 usa fila única e pacotes uRLLC podem esperar atrás de pacotes eMBB.

### 4. Variabilidade do sistema operacional

Foram observados picos de latência superiores a 1 segundo no cenário com eMBB 5M. Esses picos são causados pelo escalonador do Linux, garbage collection do Python, buffers do TCP (Nagle, delayed ACK) e contenção geral na máquina virtual.

## Conclusão

A versão original Scapy/TCP com 4 roteadores em linha e links de 2 ms **não consegue atingir latência <= 5 ms** em nenhum cenário testado. Os principais gargalos são:

1. **Atraso de propagação dos links** — responsável por ~16 ms de RTT (8 ms one-way).
2. **Overhead do BMv2 em software** — adiciona ~3–5 ms de RTT para 4 saltos.
3. **Competição com eMBB** — dobra a latência média e introduz alta variabilidade.

Mesmo removendo o eMBB e mantendo os 4 roteadores em linha com delay realista, a latência one-way fica em ~11 ms — mais que o dobro do limiar.

## Próximos passos possíveis

Para tentar melhorar a versão original **sem violar o requisito de TCP/Scapy**, as alternativas são:

1. **Reduzir o delay dos links** para valores mais realistas de rede de transporte 5G (ex.: 0,1 ms). Isso reduz diretamente o atraso de propagação.
2. **Isolar o tráfego uRLLC do eMBB** por roteamento (network slicing), mantendo 4 roteadores mas com caminho curto para uRLLC.
3. **Otimizar o pipeline P4 original** sem mudar o gerador: usar filas de prioridade (`--priority-queues 2`) para proteger o uRLLC quando o eMBB compartilha o caminho.
4. **Desativar algoritmos do TCP que aumentam a latência** (Nagle, delayed ACK) nos sockets do gerador e do receptor.
5. **Usar hardware P4 real** em vez do BMv2 em software — fora do escopo do ambiente Mininet, mas válido como discussão no artigo.

Cada uma dessas mudanças deve ser testada isoladamente para quantificar seu ganho, mantendo o gerador TCP/Scapy como principal.
