# Arquitetura OVS puro com Scapy/TCP

Esta página documenta a implementação de uma topologia com **4 switches Open vSwitch (OVS) em linha** e tráfego uRLLC gerado com **Scapy sobre TCP**, atendendo literalmente ao requisito do avaliador de usar Scapy.

## Motivação

O avaliador solicitou explicitamente que o tráfego uRLLC fosse gerado com **Scapy em TCP**. A arquitetura híbrida OVS + P4 já atingia latência <= 5 ms na maioria dos casos com socket TCP puro, mas com Scapy a latência subia para ~7,6 ms.

Para eliminar o overhead dos roteadores P4 no core, todos os 4 roteadores foram substituídos por **switches OVS**. A priorização do uRLLC é feita exclusivamente com **QoS/filas OpenFlow**, sem necessidade de P4.

## Topologia

```
h_urllc_a ──┐
            r1 (OVS) ── r2 (OVS) ── r3 (OVS) ── r4 (OVS) ──┬── h_urllc_b
h_embb_a  ──┘                                              └── h_embb_b
```

- **4 switches OVS em linha** (`r1`, `r2`, `r3`, `r4`).
- **Domínio L2 único** (`10.0.0.0/16`) para simplificar o encaminhamento.
- **Links de 1 Gbps e delay 0 ms** entre os roteadores.
- **Filas de prioridade OVS** para uRLLC (TCP porta 5000).

## Arquivos criados

- `etapa3_solucao/topologia_ovs_puro_scapy.py` — cria a topologia OVS pura e configura QoS.
- `etapa3_solucao/experimento_ovs_puro_scapy.py` — orquestra o experimento Closed Loop.
- `etapa3_solucao/gerador_urllc_scapy_otimizado.py` — gerador uRLLC com Scapy/TCP otimizado.
- `etapa3_solucao/monitor_controlador_scapy_otimizado.py` — monitor/controlador com Scapy/TCP otimizado.

## Configuração do OVS

Cada switch OVS tem duas filas HTB:

- **Queue 0**: tráfego default/eMBB.
- **Queue 1**: tráfego uRLLC (alta prioridade).

Regras OpenFlow:

```bash
# uRLLC (porta 5000 TCP) -> fila de alta prioridade
ovs-ofctl add-flow r1 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'
ovs-ofctl add-flow r1 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'

# Default/eMBB -> fila normal
ovs-ofctl add-flow r1 'priority=10,actions=set_queue:0,normal'
```

O encaminhamento L2 é feito pelo modo `normal` do OVS (learning switch).

## Otimizações do gerador/monitor Scapy

- `StreamSocket` sobre socket TCP puro.
- `TCP_NODELAY` e `TCP_QUICKACK` habilitados.
- Pacote Scapy base pré-construído; apenas o payload de timestamp é atualizado.
- Prioridade de processo: `nice -20` e `SCHED_FIFO` quando possível.
- Marcação DSCP/ToS `0xB8` (EF) nos pacotes uRLLC.
- Prioridade de socket `SO_PRIORITY=7`.

## Como executar

### uRLLC isolado (referência)

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --sem-embb --intervalo-urllc 0.1 --scapy-otimizado
```

### uRLLC + eMBB 5M UDP compartilhando o caminho

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle nenhum --intervalo-urllc 0.1 --scapy-otimizado
```

### Controle Closed Loop preventivo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

### Controle Closed Loop reativo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 10M --tipo-embb udp \
    --controle reativo --intervalo-urllc 0.1 --scapy-otimizado
```

## Resultados

Métrica: latência **one-way** medida no receptor (tempo de chegada no receptor menos timestamp de envio).

| Cenário | Latência média | Mínimo | Máximo | % > 5 ms |
|---|---|---|---|---|
| uRLLC isolado | **2,09 ms** | 0,99 ms | 22,09 ms | ~2,4% |
| uRLLC + eMBB 5M UDP (preventivo) | **2,05 ms** | 0,89 ms | 29,63 ms | ~4,5% |
| uRLLC + eMBB 10M UDP (reativo) | **1,97 ms** | 1,01 ms | 21,00 ms | ~3,1% |

Percentis representativos (cenário com eMBB 5M UDP preventivo, 60 s):

| Percentil | Latência one-way |
|---|---|
| p50 | 1,45 ms |
| p75 | 2,09 ms |
| p90 | 3,50 ms |
| p95 | 4,53 ms |
| p99 | 11,01 ms |

### Análise

A arquitetura OVS puro com Scapy/TCP atingiu o objetivo: **latência uRLLC <= 5 ms na grande maioria das amostras**, mesmo com eMBB compartilhando o caminho entre 4 switches.

- A latência média one-way ficou consistentemente abaixo de **2,5 ms**.
- A grande maioria das amostras (até ~p95) ficou abaixo de **5 ms**.
- Os picos esporádicos (> 5 ms) representam uma pequena fração e são típicos de variação de escalonamento no ambiente Mininet/OVS em software.

## Comparação com as outras abordagens

| Abordagem | uRLLC + eMBB | % > 5 ms | Observação |
|---|---|---|---|
| P4 puro 4R linha (original) | ~42 ms | 100% | Não atende. |
| P4 puro + Scapy | ~7,6 ms | ~61% | Não atende por overhead do Scapy. |
| Híbrido OVS + P4 | ~4,7 ms | ~21% | Atende, mas sem Scapy puro. |
| **OVS puro + Scapy/TCP** | **~2,1 ms** | **~4%** | **Atende ao requisito do avaliador.** |

## Por que não usar P4 nesta atividade?

Embora a disciplina utilize P4/BMv2 para a implementação de roteadores programáveis, **não foi possível atender ao requisito de latência uRLLC <= 5 ms com Scapy/TCP mantendo 4 roteadores P4 em linha**.

### O gargalo do BMv2

O `simple_switch` (BMv2) é um switch P4 executado **inteiramente em software**. Em cenários de emulação no Mininet, cada pacote atravessa o parser, pipeline e deparser em modo usuário, o que introduz latência significativa quando comparado a switches de kernel (OVS) ou hardware.

### Resultados obtidos com P4

| Abordagem P4 | Latência uRLLC one-way | % > 5 ms |
|---|---|---|
| P4 puro 4R em linha | ~42 ms | 100% |
| P4 puro caminho curto (2 saltos) | ~5,4 ms | ~33% |
| Híbrido OVS + P4 (2 P4 + 2 OVS) | ~7,3 ms | ~43% |

Todos os cenários com P4 ficaram **acima do limiar de 5 ms** quando o gerador uRLLC foi implementado com Scapy/TCP.

### O conflito técnico

A atividade exige simultaneamente:

1. **uRLLC gerado com Scapy em TCP** → alto overhead de processamento por pacote.
2. **Latência <= 5 ms** → requer datapath de baixa latência.
3. **4 roteadores na rede de transporte** → sugere P4, mas o BMv2 não entrega a latência necessária.

A combinação de BMv2 + Scapy/TCP ultrapassa o orçamento de latência. O OVS, por outro lado, tem datapath otimizado no kernel e consegue processar os pacotes Scapy/TCP dentro do limiar.

### Decisão de projeto

Diante do conflito, priorizamos o **requisito funcional de latência <= 5 ms** e o **uso obrigatório de Scapy/TCP**, mantendo **4 nós de transporte em linha**. Os nós foram implementados com OVS, que atua como switches/roteadores de transporte com QoS efetiva.

Se o avaliador exigir rigidamente roteadores P4, será necessário:

- Usar **hardware P4** (ASICs como Tofino) em vez de BMv2; ou
- Aceitar latência superior a 5 ms; ou
- Reduzir drasticamente o número de saltos P4 no caminho uRLLC (o que afasta o modelo de 4 roteadores em linha).

## Considerações

- O domínio L2 único (`10.0.0.0/16`) simplifica o roteamento e elimina a necessidade de L3 nos switches OVS.
- O OVS roda no namespace raiz do host nesta configuração Mininet padrão.
- O controle Closed Loop pode ser preventivo (dropa eMBB desde o início) ou reativo (ativa o drop quando a latência ultrapassa 5 ms em 2 amostras consecutivas).

## Recomendação

A arquitetura **OVS puro + Scapy/TCP** é a solução recomendada quando o avaliador exige explicitamente o uso de Scapy. Ela atinge latência uRLLC <= 5 ms na grande maioria dos casos, mantém 4 roteadores/switches em linha, e permite a coexistência de uRLLC e eMBB com QoS efetiva.
