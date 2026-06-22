# Comentários da Etapa 2 — Open vSwitch Básico

Este documento explica os fundamentos do Open vSwitch (OVS) e como criar uma topologia Mininet simples com switches OVS controlados por OpenFlow. O objetivo é entender as ferramentas que serão usadas na Etapa 3 antes de montar o sistema closed loop.

---

## O que é o Open vSwitch?

O **Open vSwitch (OVS)** é um switch virtual de código aberto que pode operar tanto com aprendizado automático de MACs quanto com regras programáveis via protocolo **OpenFlow**. No nosso projeto, usamos o OVS em conjunto com filas **HTB** (Hierarchical Token Bucket) para implementar QoS e priorizar o tráfego uRLLC.

### Principais componentes

- **`ovs-vswitchd`**: daemon principal que executa o switch.
- **`ovsdb-server`**: banco de dados de configuração do OVS.
- **`ovs-vsctl`**: utilitário para configurar bridges, portas e QoS.
- **`ovs-ofctl`**: utilitário para manipular regras OpenFlow.

---

## Criando uma topologia simples com OVS

A seguir, um exemplo de topologia Mininet com dois hosts e um switch OVS.

### Arquivo: `etapa1_ambiente/topologia_simples.py`

Embora esteja na pasta `etapa1_ambiente`, o script `topologia_simples.py` já usa a classe `OVSSwitch` do Mininet. Ele cria uma rede com dois hosts e um switch OVS, e testa a conectividade entre eles.

### Comando para executar

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/topologia_simples.py
```

### Parâmetros do comando

| Parâmetro | Significado |
|---|---|
| `sudo` | O Mininet precisa de privilégios de root para criar namespaces e interfaces virtuais. |
| `/root/atividade-final-redes-ppgti/.venv/bin/python3` | Interpretador Python do ambiente virtual do projeto. |
| `etapa1_ambiente/topologia_simples.py` | Script que cria a topologia e executa o teste de ping. |

### Dentro da CLI do Mininet

Após iniciar, a CLI do Mininet fica disponível. Você pode testar:

```
pingall
host_a ping -c 4 host_b
exit
```

- `pingall`: envia pings entre todos os pares de hosts.
- `host_a ping -c 4 host_b`: envia 4 pings do host_a para o host_b.
- `exit`: encerra a topologia.

---

## Verificando o estado do OVS

Fora da CLI do Mininet, em outro terminal, você pode inspecionar o switch OVS criado pelo Mininet.

### Listar bridges OVS

```bash
sudo ovs-vsctl list-br
```

Saída esperada:
```
s1
```

### Ver portas de uma bridge

```bash
sudo ovs-vsctl list-ports s1
```

Saída esperada:
```
s1-eth1
s1-eth2
```

### Ver regras OpenFlow

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Por padrão, o OVS opera em modo "normal" (learning switch), então a saída pode estar vazia ou mostrar apenas a regra padrão.

---

## Inserindo regras OpenFlow manualmente

Você pode substituir o modo de aprendizado automático por regras OpenFlow explícitas.

### Adicionar uma regra de encaminhamento

```bash
sudo ovs-ofctl -O OpenFlow13 add-flow s1 "in_port=1,actions=output:2"
sudo ovs-ofctl -O OpenFlow13 add-flow s1 "in_port=2,actions=output:1"
```

### Parâmetros das regras

| Parâmetro | Significado |
|---|---|
| `ovs-ofctl` | Utilitário de controle de fluxos OpenFlow. |
| `-O OpenFlow13` | Versão do protocolo OpenFlow (1.3). |
| `add-flow s1` | Adiciona uma regra na bridge `s1`. |
| `in_port=1` | Casa pacotes que chegam na porta 1. |
| `actions=output:2` | Encaminha os pacotes para a porta 2. |

### Remover todas as regras

```bash
sudo ovs-ofctl -O OpenFlow13 del-flows s1
```

---

## Configurando QoS/HTB manualmente

O OVS permite associar filas de prioridade às portas. Esse mecanismo será essencial na Etapa 3.

### Criar QoS com duas filas em uma porta

```bash
sudo ovs-vsctl -- set port s1-eth1 qos=@newqos \
  -- --id=@newqos create QoS type=linux-htb other-config:max-rate=1000000000 \
     queues=0=@q0,1=@q1 \
  -- --id=@q0 create Queue other-config:min-rate=1000000 other-config:max-rate=1000000000 \
  -- --id=@q1 create Queue other-config:min-rate=500000000 other-config:max-rate=1000000000
```

### Parâmetros do comando

| Parâmetro | Significado |
|---|---|
| `set port s1-eth1 qos=@newqos` | Associa uma configuração QoS à porta `s1-eth1`. |
| `type=linux-htb` | Usa o disciplinador HTB do Linux. |
| `other-config:max-rate=1000000000` | Taxa máxima da porta: 1 Gbps (em bits/s). |
| `queues=0=@q0,1=@q1` | Define duas filas identificadas pelos UUIDs `@q0` e `@q1`. |
| `Queue other-config:min-rate=...` | Taxa mínima garantida para a fila. |
| `Queue other-config:max-rate=...` | Taxa máxima permitida para a fila. |

### Usar uma fila em uma regra OpenFlow

```bash
sudo ovs-ofctl -O OpenFlow13 add-flow s1 "tcp,tp_dst=5000,actions=set_queue:1,normal"
sudo ovs-ofctl -O OpenFlow13 add-flow s1 "priority=10,actions=set_queue:0,normal"
```

- `set_queue:1`: envia o pacote para a fila 1 (alta prioridade).
- `set_queue:0`: envia o pacote para a fila 0 (prioridade normal).
- `normal`: encaminha o pacote usando o learning switch do OVS.

---

## Comandos manuais da Etapa 2

### Executar topologia simples com OVS

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/topologia_simples.py
```

### Testar latência com Scapy

```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/teste_latencia_scapy.py
```

### Limpar ambiente Mininet

```bash
sudo mn -c
```

### Limpar bridges OVS residuais

```bash
for br in $(sudo ovs-vsctl list-br); do sudo ovs-vsctl del-br $br; done
```

---

## Desafios encontrados e aprendizados

1. **Namespaces e interfaces residuais**: se um script Mininet for interrompido com `Ctrl+C`, interfaces virtuais e bridges OVS podem permanecer no sistema. Sempre execute `sudo mn -c` antes de iniciar uma nova topologia.

2. **Modo normal vs. regras OpenFlow**: o OVS pode operar como learning switch (`normal`) ou com regras explícitas. Na Etapa 3, usamos regras OpenFlow apenas para QoS (`set_queue`) e deixamos o encaminhamento L2 para o modo `normal`.

3. **HTB e `max-rate`**: valores muito altos ou muito baixos podem gerar warnings do kernel. O importante é definir uma taxa mínima (`min-rate`) adequada para a fila de alta prioridade, garantindo banda ao uRLLC.

4. **Portas do OVS**: diferente do BMv2, as portas do OVS são numeradas a partir de 1 nas regras OpenFlow. A interface `s1-eth1` é a porta 1, `s1-eth2` é a porta 2, e assim por diante.

---

## Próximos passos

Na Etapa 3, o OVS será usado para:

- Criar 4 switches em linha representando a rede de transporte 5G.
- Classificar tráfego uRLLC (TCP porta 5000) e eMBB (UDP/TCP porta 5001).
- Aplicar filas de prioridade HTB para isolar uRLLC.
- Receber comandos do controlador closed loop para descartar eMBB quando a latência ultrapassar 5 ms.
