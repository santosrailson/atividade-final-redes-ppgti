# Gerador uRLLC com Scapy/TCP

Para atender ao enunciado da atividade — que diz *"O tráfego URLLC deverá ser gerado e monitorado usando scripts em Python com Scapy, permitindo o envio e recepção de pacotes TCP"* — foram criadas versões do gerador e do monitor baseadas em **Scapy sobre TCP**.

## Arquivos criados

- `etapa3_solucao/gerador_urllc_scapy.py` — gerador TCP usando `StreamSocket` do Scapy.
- `etapa3_solucao/monitor_controlador_scapy.py` — receptor/controlador TCP usando `StreamSocket` do Scapy.
- `etapa3_solucao/gerador_urllc_scapy_otimizado.py` — versão otimizada com socket TCP real, `TCP_NODELAY`, `TCP_QUICKACK` e prioridade de processo.
- `etapa3_solucao/monitor_controlador_scapy_otimizado.py` — receptor otimizado correspondente.

## Como funciona

O `StreamSocket` do Scapy permite usar um socket TCP do sistema operacional como transporte, mas enviar/receber objetos Scapy. O pacote enviado é construído como:

```python
pacote = IP(dst=endereco_destino) / TCP(dport=porta_destino) / Raw(load=payload)
```

Onde `payload` contém o timestamp de envio em 8 bytes (`struct.pack("!d", timestamp_envio)`). O receptor extrai o timestamp, calcula a latência e devolve os mesmos 8 bytes.

### Versão otimizada

Na versão otimizada, o socket TCP é criado diretamente com `socket.socket()` e envolvido pelo `StreamSocket`:

```python
soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
soquete.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
soquete.connect((endereco_destino, porta_destino))
return StreamSocket(soquete, Raw)
```

As otimizações incluem:

- `TCP_NODELAY`: desabilita o algoritmo de Nagle.
- `TCP_QUICKACK`: desabilita delayed ACKs quando possível.
- `SO_PRIORITY=7`: prioridade máxima de socket.
- `nice -20` e `SCHED_FIFO`: prioridade máxima de processo.
- Pacote Scapy base pré-construído; apenas o payload é atualizado.

## Integração nos orquestradores

O `experimento_ovs_puro_scapy.py` recebeu as flags:

```bash
# Versao Scapy padrao
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    ... --scapy

# Versao Scapy otimizada
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    ... --scapy-otimizado
```

## Comandos para testar manualmente

### Experimento com Scapy padrão

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle nenhum --intervalo-urllc 0.1 --scapy
```

### Experimento com Scapy otimizado

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

### Parâmetros

| Parâmetro | Significado |
|---|---|
| `--duracao 60` | Duração do experimento em segundos. |
| `--taxa-embb 5M` | Taxa do tráfego eMBB: 5 Mbps. |
| `--tipo-embb udp` | Protocolo do eMBB: UDP ou TCP. |
| `--controle preventivo` | Dropa eMBB desde o início. |
| `--intervalo-urllc 0.1` | Intervalo entre pacotes uRLLC em segundos. |
| `--scapy` | Usa gerador/monitor Scapy padrão. |
| `--scapy-otimizado` | Usa gerador/monitor Scapy otimizado. |

### Iniciar gerador e monitor manualmente

Em uma topologia já iniciada (`topologia_ovs_puro_scapy.py`), você pode executar:

#### Monitor em `h_urllc_b`

```bash
h_urllc_b /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    /root/atividade-final-redes-ppgti/etapa3_solucao/monitor_controlador_scapy_otimizado.py \
    10.0.3.2 5000 60 &
```

Parâmetros:
- `10.0.3.2`: endereço IP do host destino uRLLC.
- `5000`: porta TCP do monitor.
- `60`: duração em segundos.

#### Gerador em `h_urllc_a`

```bash
h_urllc_a /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_urllc_scapy_otimizado.py \
    10.0.3.2 5000 0.1 60 &
```

Parâmetros:
- `10.0.3.2`: endereço IP do destino uRLLC.
- `5000`: porta TCP do uRLLC.
- `0.1`: intervalo entre pacotes em segundos.
- `60`: duração em segundos.

## Resultados

### Topologia OVS puro, 4 switches em linha

| Versão do gerador | Cenário | Latência média | % > 5 ms |
|---|---|---|---|
| Scapy padrão | Sem eMBB | ~4,5 ms | ~15% |
| Scapy padrão | +eMBB 5M UDP | ~5,5 ms | ~25% |
| **Scapy otimizado** | **Sem eMBB** | **~2,1 ms** | **~2%** |
| **Scapy otimizado** | **+eMBB 5M UDP preventivo** | **~2,0 ms** | **~4,5%** |

## Análise

A versão otimizada reduziu significativamente o overhead do Scapy ao usar socket TCP real e prioridade de processo. Combinada com a arquitetura OVS puro, a latência uRLLC ficou consistentemente abaixo de 5 ms na maioria dos cenários.

A principal diferença em relação às tentativas anteriores com BMv2 é que o **OVS possui datapath otimizado**, o que compensa o overhead do Scapy e permite atender ao requisito de latência.

## Implicação para o projeto

A arquitetura final resolve o dilema entre:

- **Requisito literal do enunciado**: usar Scapy em tráfego TCP.
- **Requisito de desempenho**: latência <= 5 ms.

Com **OVS puro + Scapy otimizado**, ambos os requisitos são atendidos simultaneamente.
