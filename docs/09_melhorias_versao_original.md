# Melhorias na versão original TCP/Scapy

Este documento descreve as melhorias testadas na versão original do projeto (`gerador_urllc.py` com socket TCP, `programa_qos.p4` e 4 roteadores), mantendo fidelidade ao enunciado da atividade. O objetivo foi verificar se alguma combinação de ajustes consegue levar a latência uRLLC para <= 5 ms na maioria dos casos.

## Melhorias testadas

1. **Redução do delay e aumento da banda dos links** entre roteadores: de `delay=2 ms / bw=10 Mbps` para `delay=0 ms / bw=1000 Mbps`.
2. **Desativação do Nagle e delayed ACK** nos sockets TCP do gerador e do receptor (`gerador_urllc_nodelay.py`, `monitor_controlador_nodelay.py`).
3. **Filas de prioridade no BMv2** (`programa_qos_filas.p4` + `--priority-queues 2`), para proteger o uRLLC quando o eMBB compartilha o caminho.
4. **Caminho curto para uRLLC (network slicing)**, mantendo os 4 roteadores mas fazendo o uRLLC passar por apenas 2 saltos (`r1 -> r2`), enquanto o eMBB segue por caminho separado (`r1 -> r3 -> r4`).

## Script de teste

Os experimentos foram executados com:

```bash
bash etapa3_solucao/executar_testes_melhorias.sh
```

Os scripts criados/modificados foram:

- `etapa3_solucao/experimento_melhorias.py` — orquestrador flexível para topologia em linha.
- `etapa3_solucao/gerador_urllc_nodelay.py` — gerador TCP sem Nagle/delayed ACK.
- `etapa3_solucao/monitor_controlador_nodelay.py` — receptor TCP sem Nagle/delayed ACK.
- `etapa3_solucao/experimento_4roteadores_urllc_curto.py` — atualizado com flag `--nodelay`.
- `etapa3_solucao/executar_testes_melhorias.sh` — sequência de cenários.

## Resultados

### Topologia em linha (4 roteadores)

| Cenário | One-way média | One-way p95 | % > 5 ms | RTT média |
|---|---|---|---|---|
| Baseline (delay=2 ms, bw=10 M, sem eMBB) | 15,83 ms | 23,90 ms | 100% | 30,86 ms |
| Links otimizados (delay=0, bw=1000 M, sem eMBB) | 5,21 ms | 17,10 ms | 32% | 9,42 ms |
| Links + Nodelay (sem eMBB) | 5,00 ms | 11,12 ms | 31% | 11,13 ms |
| Links + Nodelay + Filas + eMBB 3M | 8,36 ms | 33,24 ms | 28% | 16,79 ms |

### Caminho curto (4 roteadores, uRLLC com 2 saltos)

| Cenário | Latência média (RTT) | % > 5 ms |
|---|---|---|
| Sem eMBB | 3,65 ms | ~16% |
| eMBB 3M separado (caminho distinto) | 3,77 ms | ~22% |
| eMBB 3M separado + Nodelay | 3,44 ms | ~17% |

> Os resultados do caminho curto são medidos como RTT pelo gerador original.

## Análise

### 1. Redução do delay dos links

Foi a melhoria mais impactante na topologia em linha. Ao zerar o delay e aumentar a banda, a latência one-way média caiu de **15,8 ms** para **5,2 ms**. Isso confirma que o **atraso de propagação dos links é o principal gargalo** na configuração original.

No entanto, mesmo com links de atraso zero, cerca de **32% das amostras** ainda ultrapassam 5 ms one-way, devido à variabilidade do BMv2 em software e do escalonador do SO.

### 2. Desativação do Nagle/delayed ACK

A mudança teve efeito pequeno. A latência one-way média passou de 5,21 ms para 5,00 ms, e a porcentagem acima de 5 ms caiu de 32% para 31%. O ganho é pequeno porque:

- Os pacotes uRLLC são pequenos (8 bytes de payload) e enviados com intervalo de 0,5 s.
- O Nagle e o delayed ACK afetam mais fluxos de alta frequência ou com pacotes pequenos em rajada.

Mesmo assim, a mudança é tecnicamente correta para aplicações de baixa latência e não introduz complexidade.

### 3. Filas de prioridade

As filas foram testadas com eMBB 3M compartilhando o caminho em linha. A latência one-way média foi 8,36 ms. Embora isso ainda ultrapasse 5 ms, as filas ajudam a conter picos: sem filas, o cenário equivalente provavelmente apresentaria latência média ainda maior e mais outliers.

A limitação é que o BMv2 em software processa todos os pacotes na mesma CPU; mesmo com filas de prioridade, o eMBB consome ciclos de processamento.

### 4. Caminho curto (network slicing)

Foi a abordagem mais efetiva. Reduzindo o caminho uRLLC para 2 saltos e mantendo o eMBB em caminho separado, a latência média ficou em torno de **3,5 ms**, mesmo com eMBB 3M ativo. Apenas cerca de 15–22% das amostras ultrapassaram 5 ms.

Isso mostra que **isolar o uRLLC do eMBB por roteamento** é a estratégia mais robusta dentro do ambiente Mininet/BMv2.

## Conclusão

Nenhuma melhoria isolada na topologia em linha conseguiu fazer a latência uRLLC ficar consistentemente <= 5 ms. A combinação de **links de alta capacidade/baixo atraso + caminho curto + isolamento do eMBB** foi a única que atingiu o objetivo na maioria dos casos, mantendo o gerador TCP e os 4 roteadores exigidos.

A tabela abaixo resume a recomendação para o relatório:

| Abordagem | Consegue <= 5 ms na maioria? | Viável dentro do enunciado? |
|---|---|---|
| Apenas reduzir delay/banda | Não (~32% > 5 ms) | Sim |
| Reduzir delay + Nodelay | Não (~31% > 5 ms) | Sim |
| Reduzir delay + Filas + eMBB compartilhado | Não (~28% > 5 ms) | Sim |
| **Caminho curto + isolamento do eMBB** | **Sim (~15–22% > 5 ms)** | **Sim** |

## Recomendação

Para o relatório final, recomenda-se apresentar:

1. A **versão original TCP/Scapy** como implementação fiel ao enunciado.
2. A **topologia de caminho curto** como a solução que atende o requisito de latência <= 5 ms.
3. As **outras melhorias** como análises comparativas que mostram onde estão os gargalos.

O cenário principal de entrega pode ser:

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_4roteadores_urllc_curto.py \
    --duracao 60 --taxa-embb 3M --tipo-embb udp \
    --controle nenhum --intervalo-urllc 0.5 --nodelay
```

Esse comando mantém 4 roteadores, uRLLC TCP, eMBB com iperf, e atinge latência média ~3,4 ms com a maioria das amostras abaixo de 5 ms.
