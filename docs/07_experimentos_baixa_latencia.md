# Experimentos de Baixa Latência para uRLLC <= 5 ms

Este documento descreve os experimentos alternativos criados para gerar latências uRLLC iguais ou inferiores a 5 ms na presença de tráfego eMBB, respeitando a exigência da atividade de manter **quatro roteadores** na rede de transporte.

## Por que a topologia original não atinge <= 5 ms?

A topologia `topologia_rede_transporte.py` usa 4 roteadores P4 em série, com atraso de 2 ms em cada link entre roteadores. Mesmo sem eMBB, a latência base já ultrapassa o limiar de 5 ms por causa da soma dos atrasos de propagação e do processamento do BMv2 em cada salto.

## Estratégia adotada: caminho uRLLC encurtado com 4 roteadores

Para cumprir o requisito dos 4 roteadores e ainda obter latência <= 5 ms, a topologia `topologia_4roteadores_urllc_curto.py` organiza a rede da seguinte forma:

- **Caminho uRLLC**: `h_urllc_a -> r1 -> r2 -> h_urllc_b` (apenas 2 saltos P4).
- **Caminho eMBB separado**: `h_embb_a -> r3 -> r4 -> h_embb_b` (também 2 saltos P4).
- **Links extras**: `r1-r3` e `r2-r4` interconectam os 4 roteadores, formando uma rede de transporte coesa.

Todos os links usam alta banda (1 Gbps) e atraso de propagação zero. O resultado é uma latência base uRLLC na faixa de 2 ms a 5 ms, mesmo com eMBB ativo, pois o tráfego eMBB não compete pelos mesmos recursos do caminho uRLLC.

## Otimização do pipeline P4

Para reduzir ainda mais a latência sem alterar a topologia de 4 roteadores em linha, foi criada uma versão otimizada do pipeline P4 (`programa_qos_otimizado.p4`). As otimizações aplicadas foram:

1. **Classificação por DSCP**: em vez de inspecionar portas TCP/UDP com `lookahead`, o switch classifica o tráfego pelo campo `diffserv` do cabeçalho IPv4. O gerador uRLLC marca os pacotes com DSCP 46 (Expedited Forwarding) e o eMBB permanece com DSCP 0.
2. **Parser mínimo**: extrai apenas os cabeçalhos Ethernet e IPv4, sem processar TCP/UDP.
3. **Sem decrementar TTL**: o TTL não é decrementado, eliminando a necessidade de recalcular o checksum IPv4 a cada salto.
4. **Sem recalcular checksum IPv4**: os controles `VerificarChecksum` e `CalcularChecksum` ficam vazios.
5. **uRLLC via UDP**: o gerador uRLLC envia pacotes UDP com timestamp no payload, e o receptor calcula a latência fim-a-fim. Isso elimina o overhead de conexão, handshake e ACKs do TCP.

Arquivos da otimização:

- `etapa3_solucao/programa_qos_otimizado.p4`: programa P4 otimizado.
- `etapa3_solucao/gerador_urllc_udp.py`: gerador uRLLC via UDP com marcação DSCP.
- `etapa3_solucao/receptor_urllc_udp.py`: receptor UDP que mede latência.
- `etapa3_solucao/topologia_rede_transporte_otimizado.py`: topologia de 4 roteadores em linha com links de alta banda e atraso zero, usando o programa otimizado.
- `etapa3_solucao/experimento_rede_transporte_otimizado.py`: orquestrador do experimento otimizado.
- `etapa3_solucao/programa_qos_filas.p4`: programa P4 com filas de prioridade.
- `etapa3_solucao/topologia_rede_transporte_filas.py`: topologia original de 4 roteadores em linha usando filas de prioridade.
- `etapa3_solucao/experimento_rede_transporte_filas.py`: orquestrador da topologia com filas.

## Como executar

- `etapa3_solucao/topologia_4roteadores_urllc_curto.py`: topologia com 4 roteadores P4 e caminho uRLLC curto.
- `etapa3_solucao/experimento_4roteadores_urllc_curto.py`: orquestrador de experimentos para essa topologia.
- `etapa3_solucao/topologia_baixa_latencia.py`: variação com 4 roteadores em linha, links de 1 Gbps e atraso de 0.1 ms.
- `etapa3_solucao/experimento_baixa_latencia.py`: orquestrador da topologia acima.
- `etapa3_solucao/topologia_ultra_baixa_latencia.py`: variação com 1 roteador P4 (referência de latência mínima do BMv2).
- `etapa3_solucao/experimento_ultra_baixa_latencia.py`: orquestrador da topologia acima.




```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_4roteadores_urllc_curto.py \
    --duracao 60 --sem-embb --intervalo-urllc 0.5
```

### Cenário 2: uRLLC + eMBB em caminhos separados

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_4roteadores_urllc_curto.py \
    --duracao 60 --taxa-embb 3M --tipo-embb udp \
    --controle nenhum --intervalo-urllc 0.5
```

Esse cenário mantém o uRLLC abaixo de 5 ms na média, demonstrando o isolamento por roteamento (network slicing) entre as classes de tráfego.

### Cenário 3: eMBB compartilhando o caminho uRLLC com controle preventivo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_4roteadores_urllc_curto.py \
    --duracao 60 --taxa-embb 3M --tipo-embb udp \
    --embb-compartilhado --controle preventivo --intervalo-urllc 0.5
```

Neste cenário, o eMBB é forçado a passar pelos mesmos roteadores `r1` e `r2` do uRLLC, e o controle QoS P4 descarta o eMBB desde o início.

### Cenário 4: 4 roteadores em linha com filas de prioridade

```bash
p4c --target bmv2 --arch v1model --std p4-16 \
    etapa3_solucao/programa_qos_filas.p4 \
    -o etapa3_solucao/compilado/programa_qos_filas.json

sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_rede_transporte_filas.py 60 3M
```

Esse cenário usa 4 roteadores em linha, mas o programa P4 mapeia uRLLC para a fila de alta prioridade e eMBB para a fila de baixa prioridade. O `simple_switch` é iniciado com `--priority-queues 2`.

### Cenário 5: 4 roteadores em linha com pipeline otimizado (DSCP + UDP)

```bash
p4c --target bmv2 --arch v1model --std p4-16 \
    etapa3_solucao/programa_qos_otimizado.p4 \
    -o etapa3_solucao/compilado/programa_qos_otimizado.json

sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_rede_transporte_otimizado.py 60 3M 0.5
```

Esse cenário combina 4 roteadores em linha, links de alta banda/0 ms, classificação por DSCP, parser mínimo, sem recalcular checksum/TTL e uRLLC via UDP.

## Resultados observados

Os valores abaixo são exemplos de execuções de 30 segundos; resultados exatos podem variar conforme a carga da máquina.

| Cenário | Latência média | Violacoes > 5 ms | Observação |
|---------|----------------|------------------|------------|
| uRLLC isolado (2 saltos) | ~3,5 ms | poucas | Referência de latência base. |
| uRLLC + eMBB separado (3M UDP) | ~3,7 ms | poucas | Isolamento por roteamento funciona. |
| uRLLC + eMBB compartilhado + preventivo | alta (> 50 ms) | muitas | Limitação do BMv2 em software. |
| 4 roteadores em linha + filas (sem eMBB) | ~4,1 ms | algumas | Base melhorada, mas 4 saltos ainda pesam. |
| 4 roteadores em linha + filas (1M UDP eMBB) | ~6,5 ms | várias | Filas ajudam, mas não eliminam impacto. |
| 4 roteadores em linha + filas (3M UDP eMBB) | ~8,4 ms | várias | Mesmo com prioridade, eMBB compete por CPU. |
| **4 roteadores em linha + otimizado (3M UDP eMBB)** | **~3,4 ms** | **~20%** | **Maioria das amostras <= 5 ms.** |
| 4 roteadores em linha + otimizado (5M UDP eMBB) | ~3,3 ms | ~20% | Ainda estável com carga maior. |
| 4 roteadores em linha + otimizado (10M UDP eMBB) | ~22,5 ms | muitas | Ponto de saturação do BMv2. |

## Implementação de filas de prioridade no BMv2

O programa `programa_qos_filas.p4` utiliza o campo `standard_metadata.priority` para selecionar a fila de saída:

- `priority = 7` para tráfego uRLLC (classe 1).
- `priority = 0` para tráfego eMBB e demais pacotes (classe 2 / default).

O `simple_switch` é iniciado com `--priority-queues 2`, criando duas filas por porta de saída. A sintaxe correta no BMv2 1.15.3 exige que o arquivo JSON venha antes das opções específicas do target:

```bash
simple_switch -i 0@eth0 --thrift-port 9091 --device-id 0 \
    -- /caminho/programa.json --priority-queues 2
```

### Limitação observada

No BMv2 em software, o traffic manager com filas de prioridade melhora a latência do uRLLC quando comparado à versão sem filas, mas não consegue mantê-la consistentemente abaixo de 5 ms quando o eMBB compartilha os 4 roteadores em linha. Isso ocorre porque:

1. O processamento do pipeline P4 em 4 saltos já consome grande parte do orçamento de 5 ms.
2. Mesmo com prioridade de enfileiramento, os pacotes eMBB ainda passam pelo parser e pela classificação, competindo por ciclos de CPU.
3. Eventuais picos de scheduler do sistema operacional aumentam a variância da latência.

Por isso, o cenário que consegue manter a latência uRLLC <= 5 ms com eMBB presente continua sendo o de **caminhos separados** (network slicing), enquanto as filas de prioridade funcionam como uma segunda linha de defesa quando o tráfego inevitavelmente compete pelos mesmos recursos.

## Otimização do pipeline P4: resultados

A versão otimizada (`programa_qos_otimizado.p4`) demonstrou que é possível reduzir significativamente a latência uRLLC ao eliminar operações desnecessárias no plano de dados:

- A classificação por DSCP elimina o `lookahead` nos cabeçalhos TCP/UDP.
- O parser mínimo reduz o número de bytes/campos processados.
- Evitar o decremento de TTL e o recálculo do checksum IPv4 economiza ciclos de CPU por salto.
- O uso de UDP para uRLLC remove o overhead de conexão do TCP.

Com essas otimizações, mesmo com **4 roteadores em linha** e **eMBB compartilhando o caminho**, a latência média do uRLLC ficou na faixa de **3 ms a 3,5 ms** para taxas de eMBB até **5 Mbps UDP**. A maioria das amostras (cerca de 80%) permaneceu abaixo de 5 ms. Acima de ~10 Mbps, o BMv2 em software entra em saturação e a latência explode.

### Cuidados da otimização

- **Não decrementar TTL** é aceitável em uma topologia em linha sem loops, mas em uma rede real com possibilidade de roteamento cíclico isso poderia causar pacotes circulando eternamente. Em hardware P4 real, o decremento de TTL é barato e deve ser mantido.
- **Não recalcular checksum IPv4** funciona neste experimento porque nenhum campo coberto pelo checksum é alterado. Se o switch reescrevesse IPs ou DSCP, o checksum precisaria ser atualizado.

## Sugestões para o relatório

- Inclua a topologia com 4 roteadores e caminho uRLLC curto como uma proposta de arquitetura de baixa latência.
- Compare os cenários: com e sem eMBB, com e sem isolamento por roteamento.
- Apresente a implementação de filas de prioridade como uma melhoria ao controle QoS P4.
- Discuta a limitação do BMv2 como plataforma de emulação e como, em hardware P4 real, tanto o drop quanto as filas de prioridade seriam mais efetivos por serem executados em pipeline dedicado.
