# Comentários da Etapa 3 — Sistema Closed Loop para uRLLC com OVS

Este documento explica cada arquivo e cada decisão técnica tomada na Etapa 3 do projeto, agora baseada exclusivamente em **Open vSwitch (OVS)** com **OpenFlow 1.3** e **QoS/HTB**. O objetivo é complementar os códigos, que não possuem comentários inline extensos.

---

## Visão geral da solução

A Etapa 3 implementa um sistema de monitoramento e controle em malha fechada para aplicações uRLLC em uma rede de transporte 5G emulada.

Componentes principais:
- **Topologia**: 4 switches OVS em série, 2 hosts de origem (uRLLC e eMBB) e 2 hosts de destino.
- **QoS/OpenFlow**: classifica tráfego por porta TCP/UDP e direciona para filas HTB de prioridade.
- **Monitor/controlador**: roda no host destino uRLLC, mede latência e envia sinais de controle.
- **Atuador**: o script `experimento_ovs_puro_scapy.py` lê os sinais e insere/remove regras OpenFlow nos switches OVS para descartar tráfego eMBB.
- **Geradores**: tráfego uRLLC com Scapy sobre TCP e tráfego eMBB com iperf3 UDP/TCP.
- **Coleta**: salva latências em CSV e gera gráfico.

---

## Arquivo: `etapa3_solucao/topologia_ovs_puro_scapy.py`

Cria a rede de transporte 5G com quatro switches OVS em linha.

### Endereçamento

A rede opera como um único domínio L2 (`10.0.0.0/16`) para simplificar o encaminhamento e eliminar a necessidade de roteamento L3 nos switches.

**Hosts de origem:**
- `h_urllc_a`: 10.0.1.1/16, MAC 00:00:00:00:01:01
- `h_embb_a`: 10.0.2.1/16, MAC 00:00:00:00:02:01

**Hosts de destino:**
- `h_urllc_b`: 10.0.3.2/16, MAC 00:00:00:00:03:02
- `h_embb_b`: 10.0.4.2/16, MAC 00:00:00:00:04:02

**Enlaces entre switches:**
- r1-r2: 1 Gbps, atraso 0 ms
- r2-r3: 1 Gbps, atraso 0 ms
- r3-r4: 1 Gbps, atraso 0 ms

**Enlaces dos hosts:**
- hosts → switches: 100 Mbps, atraso 0 ms

### Classe `OVSSwitch`

Usamos a classe padrão do Mininet, configurada com protocolo OpenFlow 1.3. Os switches são identificados como `r1`, `r2`, `r3` e `r4` para manter a semântica de roteadores de transporte.

### Configuração de interfaces

A função `configurar_interfaces_hosts`:
- Desabilita IPv6 em todas as interfaces.
- Desabilita checksum offload (`tx-checksum-ip-generic` e `rx-checksum`).

A desativação do checksum offload é necessária porque o Linux, em ambientes virtuais, pode deixar o checksum TCP/UDP como placeholder. Sem desabilitar, o destinatário pode descartar pacotes.

### QoS/HTB

Cada porta OVS recebe uma configuração QoS com duas filas HTB:
- **Fila 0**: tráfego default/eMBB.
- **Fila 1**: tráfego uRLLC (alta prioridade).

### Regras OpenFlow

As regras instaladas em cada switch são:

```bash
# uRLLC (TCP porta 5000) -> fila 1
ovs-ofctl add-flow r1 'priority=100,tcp,tp_dst=5000,actions=set_queue:1,normal'
ovs-ofctl add-flow r1 'priority=100,tcp,tp_src=5000,actions=set_queue:1,normal'

# eMBB/default -> fila 0
ovs-ofctl add-flow r1 'priority=10,actions=set_queue:0,normal'
```

- `set_queue:1`: envia o pacote para a fila de alta prioridade.
- `set_queue:0`: envia o pacote para a fila normal.
- `normal`: usa o learning switch do OVS para encaminhamento L2.

---

## Arquivo: `etapa3_solucao/gerador_urllc_scapy_otimizado.py`

Gera tráfego uRLLC usando **Scapy sobre TCP**.

### Funcionamento

- Cria um socket TCP (`AF_INET`, `SOCK_STREAM`) e envolve com `StreamSocket` do Scapy.
- Constrói um pacote base `IP/TCP/Raw` com ToS `0xB8` (DSCP EF).
- Envia um timestamp de 8 bytes no payload (`struct.pack("!d", time.time())`).
- Aguarda a resposta do monitor.
- Calcula a latência de ida e volta (RTT).
- Reconecta automaticamente se a conexão cair.

### Otimizações aplicadas

- `TCP_NODELAY`: desabilita o algoritmo de Nagle.
- `TCP_QUICKACK`: desabilita delayed ACKs quando possível.
- `SO_PRIORITY=7`: prioridade de socket.
- `nice -20` e `SCHED_FIFO`: prioridade máxima de processo.
- Pacote Scapy base pré-construído; apenas o payload é atualizado.

---

## Arquivo: `etapa3_solucao/monitor_controlador_scapy_otimizado.py`

Roda no host `h_urllc_b` e atua como servidor TCP na porta 5000.

### Funcionamento

- Aceita conexões do gerador uRLLC usando `StreamSocket` do Scapy.
- Recebe o pacote `IP/TCP/Raw` e extrai o timestamp de envio.
- Calcula a latência unidirecional (one-way): `tempo_recebimento - tempo_envio`.
- Responde com o mesmo timestamp.
- Avalia a latência em relação ao limiar de 5 ms.
- Envia sinais de controle para o atuador via arquivo `/tmp/sinal_controle_qos`.

### Lógica de controle

- Se a latência ultrapassa 5 ms por 2 amostras consecutivas, envia sinal `ativar`.
- Se a latência fica abaixo de 5 ms por 3 amostras consecutivas, envia sinal `desativar`.

---

## Arquivo: `etapa3_solucao/gerador_embb.py`

Gera tráfego eMBB usando iperf3.

### Modo servidor

Inicia um servidor iperf na porta 5001.

### Modo cliente

Conecta ao servidor iperf e envia tráfego UDP ou TCP por uma duração especificada.

### Taxa de tráfego

O experimento usa taxas entre 3 Mbps e 10 Mbps em links de 100 Mbps/1 Gbps. O objetivo é criar congestionamento suficiente para aumentar a latência do uRLLC quando não houver controle.

---

## Arquivo: `etapa3_solucao/experimento_ovs_puro_scapy.py`

Orquestra todo o experimento Closed Loop.

### Passos

1. Cria a topologia OVS pura.
2. Inicia o monitor/controlador Scapy em `h_urllc_b`.
3. Inicia o servidor iperf em `h_embb_b`.
4. Inicia o cliente iperf em `h_embb_a`.
5. Inicia o gerador uRLLC Scapy em `h_urllc_a`.
6. Monitora o arquivo de sinal e aplica/desaplica as regras OpenFlow de drop de eMBB.
7. Aguarda o término dos processos.
8. Chama o script de coleta de resultados.

### Atuação nos switches OVS

A função `aplicar_controle_qos` usa `ovs-ofctl` para adicionar ou remover regras de drop de eMBB:

```bash
# Ativar drop de eMBB
ovs-ofctl add-flow r1 'priority=200,udp,tp_dst=5001,actions=drop'

# Desativar drop de eMBB
ovs-ofctl del-flows r1 'udp,tp_dst=5001'
```

A função `monitorar_sinal_e_atuar` verifica o arquivo `/tmp/sinal_controle_qos` periodicamente e aplica a ação correspondente em todos os switches.

---

## Arquivo: `etapa3_solucao/coletar_resultados.py`

Lê o arquivo CSV de latências (`/tmp/latencias_urllc.csv`) e gera estatísticas e gráfico.

### Estatísticas calculadas

- Quantidade de amostras
- Latência média
- Latência mínima
- Latência máxima
- Quantidade de violações acima de 5 ms

### Gráfico

Gera um gráfico de linha com as latências ao longo do tempo, incluindo:
- linha tracejada no limiar de 5 ms;
- marcações dos eventos de controle (ativar/desativar).

---

## Comandos manuais da Etapa 3

### Executar o experimento completo

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb udp \
    --controle preventivo --intervalo-urllc 0.1 --scapy-otimizado
```

### Parâmetros do experimento

| Parâmetro | Obrigatório | Valor padrão | Significado |
|---|---|---|---|
| `--duracao` | Não | `60` | Duração total do experimento em segundos. |
| `--taxa-embb` | Não | `3M` | Taxa do tráfego eMBB (ex: `3M`, `5M`, `10M`). |
| `--tipo-embb` | Não | `udp` | Protocolo do eMBB: `udp` ou `tcp`. |
| `--controle` | Não | `nenhum` | Modo de controle: `nenhum`, `preventivo` ou `reativo`. |
| `--intervalo-urllc` | Não | `0.5` | Intervalo entre pacotes uRLLC em segundos. |
| `--sem-embb` | Não | `False` | Se presente, executa apenas uRLLC sem tráfego de fundo. |
| `--scapy-otimizado` | Não | `False` | Se presente, usa gerador/monitor Scapy otimizado. |

#### Explicação dos modos de controle

- `nenhum`: executa o experimento sem drop de eMBB. Serve como baseline.
- `preventivo`: dropa eMBB desde o início do experimento.
- `reativo`: monitora a latência e ativa o drop apenas quando houver 2 violações consecutivas acima de 5 ms.

#### Exemplo com controle reativo e eMBB TCP

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 60 --taxa-embb 5M --tipo-embb tcp \
    --controle reativo --intervalo-urllc 0.1 --scapy-otimizado
```

#### Exemplo sem eMBB

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/experimento_ovs_puro_scapy.py \
    --duracao 30 --sem-embb --intervalo-urllc 0.1 --scapy-otimizado
```

---

### Executar a topologia sem o experimento (abre CLI do Mininet)

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/topologia_ovs_puro_scapy.py
```

Dentro da CLI do Mininet, você pode testar:

```
pingall
h_urllc_a ping -c 4 h_urllc_b
h_embb_a ping -c 4 h_embb_b
exit
```

---

### Iniciar o experimento manualmente (componentes separados)

Se quiser controlar cada componente individualmente, inicie a topologia primeiro:

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/topologia_ovs_puro_scapy.py
```

Na CLI do Mininet, execute cada componente em background:

#### 1. Iniciar monitor/controlador Scapy em `h_urllc_b`

```bash
h_urllc_b /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    /root/atividade-final-redes-ppgti/etapa3_solucao/monitor_controlador_scapy_otimizado.py \
    10.0.3.2 5000 60 &
```

Parâmetros:
- `10.0.3.2`: endereço IP do host destino uRLLC.
- `5000`: porta TCP do monitor.
- `60`: duração em segundos.

#### 2. Iniciar servidor iperf em `h_embb_b`

```bash
h_embb_b /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py servidor &
```

#### 3. Iniciar cliente iperf em `h_embb_a`

```bash
h_embb_a /root/atividade-final-redes-ppgti/.venv/bin/python3 \
    /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py \
    cliente 10.0.4.2 5001 60 5M udp &
```

Parâmetros:
- `cliente`: modo de operação.
- `10.0.4.2`: endereço IP do servidor iperf.
- `5001`: porta UDP/TCP do eMBB.
- `60`: duração em segundos.
- `5M`: taxa de tráfego.
- `udp`: protocolo (`udp` ou `tcp`).

#### 4. Iniciar gerador uRLLC Scapy em `h_urllc_a`

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

#### 5. Gerar gráfico a partir de resultados salvos

```bash
/root/atividade-final-redes-ppgti/.venv/bin/python3 \
    etapa3_solucao/coletar_resultados.py \
    /tmp/latencias_urllc.csv \
    /tmp/grafico_latencias.png \
    /tmp/eventos_controle.txt
```

Parâmetros:
- `/tmp/latencias_urllc.csv`: arquivo CSV com as latências medidas.
- `/tmp/grafico_latencias.png`: caminho do gráfico de saída.
- `/tmp/eventos_controle.txt`: arquivo com eventos de ativação/desativação do controle.

---

### Limpar ambiente Mininet

```bash
sudo mn -c
```

### Limpar bridges OVS residuais

```bash
for br in $(sudo ovs-vsctl list-br); do sudo ovs-vsctl del-br $br; done
```

### Limpar interfaces virtuais residuais

```bash
for iface in $(ip -o link show | awk -F': ' '{print $2}' | grep -E '^(r[1-4]-eth|h_[a-z_]+-eth)'); do
    sudo ip link del $iface 2>/dev/null || true
done
```

---

## Desafios encontrados e aprendizados

1. **Overhead do Scapy**: o Scapy introduz latência extra no gerador e no monitor. Por isso, aplicamos otimizações como `StreamSocket`, pacote base pré-construído e prioridade de processo.

2. **Namespaces e interfaces residuais**: se um script Mininet for interrompido com `Ctrl+C`, interfaces virtuais e bridges OVS podem permanecer no sistema. Sempre execute `sudo mn -c` antes de iniciar uma nova topologia.

3. **QoS/HTB no OVS**: a configuração das filas HTB pode gerar warnings do kernel (`quantum of class is big`), mas isso não impede o funcionamento. O importante é garantir que a fila 1 tenha `min-rate` alto o suficiente para priorizar o uRLLC.

4. **Latência one-way vs. RTT**: o gerador mede RTT, enquanto o monitor mede latência one-way. O arquivo final `/tmp/latencias_urllc.csv` usa a medição one-way do monitor, que é mais representativa para uRLLC.

5. **Controle preventivo vs. reativo**: o modo preventivo garante latência baixa desde o início, mas impede a medição do momento de ativação do controle. O modo reativo mostra o closed loop funcionando, mas pode permitir algumas violações antes da ativação.
