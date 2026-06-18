# Documentação do Projeto — Sistema de Monitoramento e Controle para uRLLC

Este arquivo descreve a estrutura inicial do projeto, a forma como cada componente foi implementado e os comandos necessários para executar a topologia de rede em Mininet com switches programáveis P4.

---

## 1. Visão Geral

O projeto emula uma rede de transporte 5G que transporta duas classes de tráfego distintas:

- **uRLLC** (*Ultra-Reliable Low Latency Communication*): tráfego sensível à latência, cujo atraso fim-a-fim deve ser mantido abaixo de **5 ms**.
- **eMBB** (*enhanced Mobile Broadband*): tráfego de alta demanda de banda, que pode tolerar maior latência.

A emulação é feita no **Mininet**, os switches são implementados com o modelo P4 **v1model** usando o **simple_switch** (comportamental model v2) e o plano de dados é programado na linguagem **P4_16**. A separação entre uRLLC e eMBB é feita por meio de portas TCP e da marcação do campo **DSCP** no cabeçalho IPv4.

---

## 2. Tecnologias Implementadas

| Tecnologia | Função |
|---|---|
| **Mininet** | Emulação da topologia de rede, hosts e switches. |
| **P4 / p4c** | Linguagem e compilador para programar o plano de dados dos switches. |
| **simple_switch** | Executável do behavioral model que interpreta o programa P4 compilado. |
| **simple_switch_CLI** | Interface de linha de comando para carregar tabelas e regras nos switches em execução. |
| **Python 3** | Orquestração da topologia Mininet e scripts de tráfego/controle. |
| **Scapy** | Geração e medição de pacotes TCP uRLLC (será utilizado nas próximas etapas). |
| **iperf / ffmpeg** | Geração de tráfego eMBB de alta banda (será utilizado nas próximas etapas). |
| **tc (traffic control)** | Ajuste dinâmico de filas e prioridades nas interfaces dos switches (será utilizado no controle em closed loop). |

---

## 3. Estrutura de Diretórios

```
.
├── .gitignore
├── README.md
├── doc_project.md
├── mininet/
│   └── topologia.py              # Topologia Mininet com 4 switches P4 e 4 hosts
├── p4/
│   ├── comutador.p4              # Código P4 do plano de dados
│   └── tabelas/
│       ├── c1.txt                # Regras de encaminhamento/classificação do switch c1
│       ├── c2.txt                # Regras de encaminhamento/classificação do switch c2
│       ├── c3.txt                # Regras de encaminhamento/classificação do switch c3
│       └── c4.txt                # Regras de encaminhamento/classificação do switch c4
├── traffic/
│   ├── urllc/                    # Scripts Scapy de tráfego uRLLC (em desenvolvimento)
│   └── embb/                     # Scripts iperf/ffmpeg de tráfego eMBB (em desenvolvimento)
├── control/                      # Scripts de controle em closed loop (em desenvolvimento)
├── util/
│   └── executar_topologia.sh     # Script auxiliar para subir a topologia
├── results/                      # Logs e resultados dos experimentos
└── docs/                         # Relatório e documentação do artigo
```

---

## 4. Topologia de Rede

A topologia é composta por **quatro switches P4** dispostos em linha e **quatro hosts**, dois para uRLLC e dois para eMBB.

```
 h_urllc_1                      h_urllc_2
   |                                |
  c1 ------ c2 ------ c3 ------ c4
   |          |          |          |
            h_embb_1   h_embb_2
```

### 4.1 Switches

| Nome | Porta 1 | Porta 2 | Porta 3 |
|---|---|---|---|
| **c1** | c2 | h_urllc_1 | — |
| **c2** | c1 | c3 | h_embb_1 |
| **c3** | c2 | c4 | h_embb_2 |
| **c4** | c3 | h_urllc_2 | — |

### 4.2 Hosts

| Nome | Endereço IP | MAC | Gateway | Classe |
|---|---|---|---|---|
| **h_urllc_1** | 10.0.1.10/16 | 00:00:00:00:01:10 | 10.0.1.1 | uRLLC |
| **h_embb_1** | 10.0.2.10/16 | 00:00:00:00:02:10 | 10.0.2.1 | eMBB |
| **h_embb_2** | 10.0.3.10/16 | 00:00:00:00:03:10 | 10.0.3.1 | eMBB |
| **h_urllc_2** | 10.0.4.10/16 | 00:00:00:00:04:10 | 10.0.4.1 | uRLLC |

### 4.3 Enlaces entre Switches

| Enlace | Portas | MACs configurados |
|---|---|---|
| c1 ↔ c2 | c1:1 → c2:1 | 00:00:00:00:12:01 / 00:00:00:00:12:02 |
| c2 ↔ c3 | c2:2 → c3:1 | 00:00:00:00:23:01 / 00:00:00:00:23:02 |
| c3 ↔ c4 | c3:2 → c4:1 | 00:00:00:00:34:01 / 00:00:00:00:34:02 |

---

## 5. Funcionamento do Código P4 (`p4/comutador.p4`)

O programa P4 define um switch L3 simples com classificação de tráfego por porta TCP.

### 5.1 Cabeçalhos

O parser reconhece três cabeçalhos:

- **ethernete_t**: endereços MAC e tipo Ethernet.
- **ipv4_t**: cabeçalho IPv4, incluindo o campo `servicos_diferenciados` (DSCP).
- **tcp_t**: cabeçalho TCP, incluindo as portas de origem e destino.

### 5.2 Parser

O parser extrai o cabeçalho Ethernet. Se o tipo for `0x0800` (IPv4), extrai o cabeçalho IPv4. Se o protocolo for `0x06` (TCP), extrai o cabeçalho TCP. Qualquer outro pacote é aceito sem processamento adicional.

### 5.3 Verificador de Soma

O controle `verificador_soma` recalcula a soma de verificação do cabeçalho IPv4 após as modificações feitas no plano de dados. Isso é necessário porque o campo DSCP e o TTL são alterados durante o processamento.

### 5.4 Ingresso

O ingresso executa duas tabelas:

#### 5.4.1 Tabela de Classificação

A tabela `tabela_classificacao` identifica o tráfego com base no **endereço IP de origem** e na **porta TCP de destino**:

| IP de Origem | Porta TCP | Ação | Prioridade | DSCP |
|---|---|---|---|---|
| 10.0.1.10 ou 10.0.4.10 | 5000 | `classificar_urllc` | 7 (máxima) | 46 (EF — Expedited Forwarding) |
| 10.0.2.10 ou 10.0.3.10 | 5001 | `classificar_embb` | 1 (baixa) | 0 (Best Effort) |

A classificação altera o campo DSCP do cabeçalho IPv4, permitindo que os próximos nós da rede (ou o próprio controle em closed loop) identifiquem a classe de serviço do pacote.

#### 5.4.2 Tabela de Encaminhamento IPv4

A tabela `tabela_encaminhamento_ipv4` realiza o roteamento com base no **endereço IP de destino** (match LPM — *Longest Prefix Match*). A ação `encaminhar` define a porta de saída e substitui o MAC de destino Ethernet pelo MAC do próximo salto. Pacotes sem rota correspondente são descartados.

### 5.5 Egresso

O bloco de egresso está reservado para futuras ações de controle, como marcação adicional, contagem de pacotes ou aplicação de políticas de fila.

### 5.6 Deparser

O deparser remonta o pacote na ordem: Ethernet, IPv4, TCP.

---

## 6. Funcionamento da Topologia Mininet (`mininet/topologia.py`)

O script cria a topologia, compila o programa P4 e carrega as tabelas de cada switch.

### 6.1 Compilação do Comutador

Ao iniciar, o método `compilar_comutador` verifica se o arquivo `p4/comutador.json` já existe. Caso contrário, executa o compilador `p4c-bm2-ss` para gerar o JSON a partir do arquivo `p4/comutador.p4`. O JSON gerado é o programa de plano de dados carregado pelo `simple_switch`.

### 6.2 Criação dos Nós

A classe `TopologiaTransporte5G` herda de `Topo` e constrói:

- Quatro switches do tipo `P4Switch`.
- Quatro hosts do tipo `P4Host`.
- Os enlaces físicos entre hosts e switches e entre os próprios switches.

### 6.3 Configuração de ARP

Como os switches P4 não respondem a requisições ARP, a função `configurar_arp_hosts` adiciona entradas ARP estáticas em cada host logo após a inicialização da rede. Cada host recebe o mapeamento entre o endereço IP do seu gateway padrão e um MAC padronizado para a interface do switch de acesso.

| Host | Gateway | MAC do Gateway |
|---|---|---|
| h_urllc_1 | 10.0.1.1 | 00:00:00:00:01:01 |
| h_embb_1 | 10.0.2.1 | 00:00:00:00:02:01 |
| h_embb_2 | 10.0.3.1 | 00:00:00:00:03:01 |
| h_urllc_2 | 10.0.4.1 | 00:00:00:00:04:01 |

### 6.4 Configuração das Tabelas

Após `rede.start()` e a configuração de ARP, a função `configurar_tabelas` percorre cada switch e executa o `simple_switch_CLI` com as regras correspondentes ao nome do switch. Isso popula as tabelas de classificação e encaminhamento em tempo de execução.

### 6.5 Parâmetros de Execução

O script aceita os seguintes argumentos:

| Argumento | Descrição |
|---|---|
| `--comportamento` | Caminho do executável do switch P4 (padrão: `simple_switch`). |
| `--pcap-dump` | Habilita a captura de pacotes nos switches. |
| `--cli` | Abre o console interativo do Mininet após a inicialização. |

---

## 7. Funcionamento das Tabelas de Encaminhamento

Cada arquivo em `p4/tabelas/` possui três partes:

1. **Ações padrão**: define o descarte como ação padrão da tabela de encaminhamento e `NoAction` para a tabela de classificação.
2. **Regras de classificação**: associam os fluxos uRLLC e eMBB às ações correspondentes.
3. **Regras de encaminhamento**: mapeiam cada endereço IP destino para a porta de saída e o MAC do próximo salto.

A seguir, um resumo das rotas:

- **c1**: pacotes para `h_urllc_1` saem pela porta 2; pacotes para os demais hosts saem pela porta 1 em direção a `c2`.
- **c2**: pacotes para `h_urllc_1` saem pela porta 1 (c1); pacotes para `h_embb_1` saem pela porta 3; pacotes para `h_embb_2` e `h_urllc_2` saem pela porta 2 (c3).
- **c3**: pacotes para `h_urllc_1` e `h_embb_1` saem pela porta 1 (c2); pacotes para `h_embb_2` saem pela porta 3; pacotes para `h_urllc_2` saem pela porta 2 (c4).
- **c4**: pacotes para `h_urllc_2` saem pela porta 2; pacotes para os demais hosts saem pela porta 1 em direção a `c3`.

---

## 8. Comandos para Execução

### 8.1 Requisitos

Antes de executar, certifique-se de que os seguintes componentes estão instalados:

- Mininet
- p4c (compilador P4)
- simple_switch (behavioral model)
- simple_switch_CLI
- Python 3 e o módulo `p4_mininet`

### 8.2 Subir a Topologia

Opção 1 — usando o script auxiliar:

```bash
./util/executar_topologia.sh
```

Opção 2 — chamando o script Python diretamente:

```bash
sudo python3 mininet/topologia.py --cli
```

> O Mininet requer privilégios de root para criar interfaces e namespaces de rede.

### 8.3 Opções Adicionais

```bash
sudo python3 mininet/topologia.py --cli --pcap-dump
```

Habilita a captura de pacotes nos switches.

```bash
sudo python3 mininet/topologia.py --comportamento /caminho/para/simple_switch --cli
```

Utiliza um caminho alternativo para o executável do switch P4.

### 8.4 Testes Básicos no CLI do Mininet

Após subir a topologia com `--cli`, é possível executar comandos como:

```bash
h_urllc_1 ping -c 3 h_urllc_2
h_urllc_1 ping -c 3 h_embb_1
```

Para testar o plano de dados P4, os scripts de tráfego uRLLC e eMBB serão adicionados na pasta `traffic/`.

---

## 9. Tráfego uRLLC com Scapy (`traffic/urllc/urllc.py`)

O script `urllc.py` gera e mede pacotes TCP uRLLC usando a biblioteca Scapy. Ele pode operar em três modos: gerador, receptor ou par.

### 9.1 Modos de Operação

| Modo | Função |
|---|---|
| **gerador** | Envia pacotes TCP periodicamente para um destino. |
| **receptor** | Escuta na porta 5000, calcula a latência one-way e responde ao emissor. |
| **par** | Envia um pacote e aguarda a resposta para calcular o RTT (*Round-Trip Time*). |

### 9.2 Estrutura do Pacote

Cada pacote uRLLC é composto por:

- Cabeçalho Ethernet com MAC de origem e destino.
- Cabeçalho IPv4 com campo DSCP definido como 46 (EF — *Expedited Forwarding*).
- Cabeçalho TCP com flags `PA` (PUSH+ACK) na porta 5000.
- Payload contendo o timestamp de envio em nanosegundos, seguido de dados opcionais.

### 9.3 Cálculo da Latência

- **Latência one-way**: o receptor compara o timestamp recebido no payload com o timestamp local no momento da chegada.
- **RTT**: o modo `par` envia um pacote, o receptor devolve o mesmo payload, e o emissor mede o tempo total de ida e volta.

### 9.4 Limiar de Alerta

O limiar de 5 ms está definido como `5_000_000` nanosegundos. Sempre que a latência medida ultrapassa esse valor, o script imprime o status `ALERTA_LIMIAR`.

### 9.5 Comandos de Execução

Dentro do CLI do Mininet, em um host:

```bash
h_urllc_2 python3 /root/atividade-final-redes-ppgti/traffic/urllc/urllc.py --modo receptor
```

Em outro terminal do mesmo host ou em outro host:

```bash
h_urllc_1 python3 /root/atividade-final-redes-ppgti/traffic/urllc/urllc.py --modo gerador --destino 10.0.4.10 --intervalo 0.5 --quantidade 100
```

Para medição de RTT:

```bash
h_urllc_1 python3 /root/atividade-final-redes-ppgti/traffic/urllc/urllc.py --modo par --destino 10.0.4.10 --intervalo 0.5 --quantidade 100
```

### 9.6 Observações sobre Captura de Pacotes

O receptor adiciona uma regra do `iptables` para descartar pacotes TCP na porta 5000, evitando que o kernel envie pacotes RST e interfira na captura realizada pelo Scapy. A regra é removida ao encerrar o receptor.

---

## 10. Próximos Passos

A estrutura inicial entrega a topologia, o plano de dados P4 e o script Scapy de tráfego uRLLC. As próximas etapas incluem:

1. Criar scripts iperf/ffmpeg para geração de tráfego eMBB.
2. Implementar o mecanismo de monitoramento em closed loop.
3. Criar o script de controle que ajusta filas e prioridades quando a latência ultrapassar 5 ms.
4. Coletar logs e resultados na pasta `results/`.
5. Escrever o relatório no formato de artigo da SBC.

---

## 11. Observações Finais

- Todo o código-fonte utiliza nomes de variáveis e funções em português para facilitar o entendimento e a manutenção manual.
- Não foram inseridos comentários dentro do código-fonte; toda a explicação está concentrada neste documento.
- Os MACs e endereços IP foram padronizados para simplificar a depuração e a reescrita das tabelas.
- O projeto está preparado para receber o controle closed loop sem alterações na topologia já criada.
