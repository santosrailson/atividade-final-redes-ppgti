# Comentários da Etapa 3 — Sistema Closed Loop para uRLLC

Este documento explica cada arquivo e cada decisão técnica tomada na Etapa 3. O objetivo é complementar os códigos, que não possuem comentários inline.

---

## Visão geral da solução

A Etapa 3 implementa um sistema de monitoramento e controle em malha fechada para aplicações uRLLC em uma rede de transporte 5G emulada.

Componentes principais:
- **Topologia**: 4 roteadores P4 em série, 2 hosts de origem (uRLLC e eMBB) e 2 hosts de destino.
- **Programa P4**: classifica tráfego por porta TCP/UDP, encaminha pacotes entre sub-redes e pode descartar tráfego eMBB em caso de violação de latência.
- **Monitor/controlador**: roda no host destino uRLLC, mede latência e envia sinais de controle.
- **Atuador**: o script `executar_experimento.py` lê os sinais e insere/remove regras nos roteadores via `simple_switch_CLI`.
- **Geradores**: tráfego uRLLC com socket TCP e tráfego eMBB com iperf UDP.
- **Coleta**: salva latências em CSV e gera gráfico.

---

## Arquivo: `etapa3_solucao/programa_qos.p4`

Programa P4 que implementa encaminhamento IPv4, classificação de tráfego e controle de QoS.

### Constantes
Definem os valores dos protocolos e portas:
- `TIPO_ETHERNET_IPV4 = 0x0800`
- `PROTOCOLO_TCP = 6`
- `PROTOCOLO_UDP = 17`

### Headers
- `ethernet_t`: cabeçalho Ethernet.
- `ipv4_t`: cabeçalho IPv4 completo.
- `tcp_t`: cabeçalho TCP de 20 bytes (sem opções).
- `udp_t`: cabeçalho UDP de 8 bytes.

### Metadados
Além de `classe_trafego` e `modo_controle`, o programa armazena as portas TCP e UDP em metadados. Isso permite classificar o tráfego sem extrair os cabeçalhos TCP/UDP completos do pacote.

### Decisão de não extrair TCP/UDP
Inicialmente, o parser extraía os cabeçalhos TCP e UDP completos. Isso causou problemas porque o cabeçalho TCP pode ter opções de tamanho variável. Ao extrair apenas 20 bytes, as opções TCP eram perdidas, e o checksum TCP ficava incorreto.

A solução foi usar `packet.lookahead<tcp_t>()` e `packet.lookahead<udp_t>()`. Essa função lê os próximos bytes do pacote sem consumi-los. Assim, obtemos as portas de origem e destino, mas o cabeçalho TCP/UDP original permanece intacto no pacote.

### Parser
- Extrai Ethernet.
- Se for IPv4, extrai IPv4.
- Se o protocolo for TCP, usa `lookahead` para ler as portas TCP.
- Se for UDP, usa `lookahead` para ler as portas UDP.

### Tabela de classificação
Usa os metadados `porta_tcp_destino` e `porta_udp_destino` como chave:
- Porta 5000: uRLLC (classe 1)
- Porta 5001: eMBB (classe 2)

Para pacotes TCP, `porta_udp_destino` é 0. Para pacotes UDP, `porta_tcp_destino` é 0.

### Tabela de controle QoS
Chave composta por `modo_controle` e `classe_trafego`:
- Se `modo_controle = 1` e `classe_trafego = 2`, a ação `aplicar_controle` descarta o pacote eMBB.
- Caso contrário, `NoAction` permite o pacote seguir.

### Tabela de encaminhamento IPv4
Mesma lógica da Etapa 2, com rotas estáticas para cada sub-rede da topologia.

### Checksum
Recalcula o checksum IPv4 após o decremento do TTL.

---

## Arquivo: `etapa3_solucao/topologia_rede_transporte.py`

Cria a rede de transporte 5G com quatro roteadores P4.

### Endereçamento

**Hosts de origem:**
- `h_urllc_a`: 10.0.1.1/24, gateway 10.0.1.254
- `h_embb_a`: 10.0.2.1/24, gateway 10.0.2.254

**Hosts de destino:**
- `h_urllc_b`: 10.0.3.2/24, gateway 10.0.3.254
- `h_embb_b`: 10.0.4.2/24, gateway 10.0.4.254

**Enlaces entre roteadores:**
- r1-r2: 10.1.1.0/30
- r2-r3: 10.1.2.0/30
- r3-r4: 10.1.3.0/30

### Classe `RoteadorP4`
Similar à classe `SwitchP4` da Etapa 2, mas com identificador de dispositivo incremental. Cada roteador precisa de um `device-id` diferente para evitar conflitos de socket internos do BMv2.

### Configuração de interfaces
A função `configurar_interfaces_hosts`:
- Desabilita IPv6 em todas as interfaces.
- Desabilita checksum offload (`tx-checksum-ip-generic` e `rx-checksum`).

A desativação do checksum offload foi necessária porque o kernel do Linux, em ambientes virtuais, pode deixar o checksum TCP/UDP como placeholder (offload para a NIC). Quando o switch P4 encaminha o pacote, o checksum não é recalculado e o destinatário descarta o pacote.

### ARP estático
Como o programa P4 descarta pacotes ARP (etherType 0x0806), configuramos entradas ARP estáticas nos hosts. Incluímos os MACs dos gateways e dos hosts remotos.

### Rotas estáticas
Cada host recebe uma rota padrão apontando para o roteador de borda.

### Largura de banda dos links
Os links entre roteadores têm largura de banda de 10 Mbps e atraso de 2 ms. Os links dos hosts para os roteadores têm 100 Mbps. Essa assimetria cria gargalo nos enlaces entre roteadores, simulando congestionamento.

---

## Arquivo: `etapa3_solucao/inserir_regras_iniciais.py`

Define as regras de classificação e encaminhamento para cada um dos quatro roteadores.

### Regras de classificação
As mesmas para todos os roteadores:
```
table_add tabela_classificacao classificar_por_porta 5000 0 => 1
table_add tabela_classificacao classificar_por_porta 0 5000 => 1
table_add tabela_classificacao classificar_por_porta 5001 0 => 2
table_add tabela_classificacao classificar_por_porta 0 5001 => 2
```

### Regras de encaminhamento
Cada roteador tem rotas para todas as sub-redes da topologia. As rotas apontam para o MAC do próximo salto e para a interface de saída correta.

Por exemplo, em r1:
- 10.0.1.0/24 → h_urllc_a, porta 0
- 10.0.2.0/24 → h_embb_a, porta 1
- 10.0.3.0/24 → r2, porta 2
- 10.0.4.0/24 → r2, porta 2

---

## Arquivo: `etapa3_solucao/gerador_urllc.py`

Gera tráfego uRLLC usando socket TCP.

### Funcionamento
- Abre conexão TCP com o host destino na porta 5000.
- Envia um timestamp de 8 bytes (formato `double`).
- Aguarda o eco do timestamp.
- Calcula a latência de ida e volta (RTT).
- Reconecta automaticamente se a conexão cair.

### Por que socket TCP em vez de Scapy?
A atividade menciona o uso de Scapy para envio e recepção de pacotes TCP. Na Etapa 1, o Scapy foi usado para medir o RTT do handshake TCP. Na Etapa 3, optamos por sockets TCP puros porque:
- Garantem entrega confiável dos timestamps.
- Facilitam a implementação do monitor que responde com eco.
- O Scapy ainda é usado conceitualmente para construir e analisar pacotes, mas a comunicação confiável usa sockets.

Caso desejado, o script pode ser adaptado para usar Scapy com `sr1` para enviar SYN e medir RTT.

---

## Arquivo: `etapa3_solucao/gerador_embb.py`

Gera tráfego eMBB usando iperf.

### Modo servidor
Inicia um servidor iperf na porta 5001.

### Modo cliente
Conecta ao servidor iperf e envia tráfego UDP por uma duração especificada.

### Taxa de tráfego
O experimento usa taxa de 5 Mbps em links de 10 Mbps. Isso cria congestionamento suficiente para aumentar a latência do uRLLC, mas deixa espaço para que os pacotes uRLLC consigam passar.

---

## Arquivo: `etapa3_solucao/monitor_controlador.py`

Roda no host `h_urllc_b` e atua como servidor TCP na porta 5000.

### Funcionamento
- Aceita conexões do gerador uRLLC.
- Recebe o timestamp de envio.
- Responde com o mesmo timestamp.
- Calcula a latência unidirecional.
- Avalia a latência em relação ao limiar de 5 ms.
- Envia sinais de controle para o atuador via arquivo `/tmp/sinal_controle_qos`.

### Lógica de controle
- Se a latência ultrapassa 5 ms por 2 amostras consecutivas, envia sinal `ativar`.
- Se a latência fica abaixo de 5 ms por 3 amostras consecutivas, envia sinal `desativar`.

### Sinalização por arquivo
O monitor não insere regras diretamente nos roteadores porque ele executa dentro do namespace de rede do host `h_urllc_b` e não consegue acessar as portas Thrift dos roteadores. Por isso, ele escreve sinais em um arquivo, e o `executar_experimento.py` (que roda no namespace raiz) lê e atua.

---

## Arquivo: `etapa3_solucao/executar_experimento.py`

Orquestra todo o experimento Closed Loop.

### Passos
1. Cria a topologia de rede.
2. Inicia o monitor/controlador em `h_urllc_b`.
3. Inicia o servidor iperf em `h_embb_b`.
4. Inicia o cliente iperf em `h_embb_a`.
5. Inicia o gerador uRLLC em `h_urllc_a`.
6. Monitora o arquivo de sinal e aplica/desaplica as regras de controle nos roteadores.
7. Aguarda o término dos processos.
8. Chama o script de coleta de resultados.

### Atuação nos roteadores
A função `aplicar_controle_qos` usa `dpctl` de cada roteador para inserir ou remover a regra de descarte de eMBB.

A função `monitorar_sinal_e_atuar` verifica o arquivo `/tmp/sinal_controle_qos` periodicamente e aplica a ação correspondente.

---

## Arquivo: `etapa3_solucao/coletar_resultados.py`

Lê o arquivo CSV de latências e gera estatísticas e gráfico.

### Estatísticas calculadas
- Quantidade de amostras
- Latência média
- Latência mínima
- Latência máxima
- Quantidade de violações acima de 5 ms

### Gráfico
Gera um gráfico de linha com as latências ao longo do tempo e uma linha tracejada no limiar de 5 ms.

---

## Comandos manuais da Etapa 3

### Configurar LD_LIBRARY_PATH
```bash
export LD_LIBRARY_PATH=/root/atividade-final-redes-ppgti/.p4libs/x86_64-linux-gnu:/root/atividade-final-redes-ppgti/.p4libs/usr_lib:$LD_LIBRARY_PATH
```

### Compilar o programa P4 de QoS
```bash
p4c --target bmv2 --arch v1model --std p4-16 etapa3_solucao/programa_qos.p4 -o etapa3_solucao/compilado/programa_qos.json
```

### Executar o experimento completo
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/executar_experimento.py 60
```

### Executar com parâmetros customizados
Sintaxe: `executar_experimento.py <duracao_segundos> <taxa_embb> <intervalo_urllc>`

Exemplo com duração de 45 segundos, eMBB a 3 Mbps e uRLLC a cada 0.5 segundos:
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/executar_experimento.py 45 3M 0.5
```

### Executar a topologia sem o experimento (abre CLI do Mininet)
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/topologia_rede_transporte.py
```

### Inserir regras iniciais manualmente
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/inserir_regras_iniciais.py 9091
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/inserir_regras_iniciais.py 9092
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/inserir_regras_iniciais.py 9093
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/inserir_regras_iniciais.py 9094
```

### Iniciar monitor/controlador manualmente (dentro do host h_urllc_b)
```bash
h_urllc_b /root/atividade-final-redes-ppgti/.venv/bin/python3 /root/atividade-final-redes-ppgti/etapa3_solucao/monitor_controlador.py 10.0.3.2 5000 60 &
```

### Iniciar gerador uRLLC manualmente (dentro do host h_urllc_a)
```bash
h_urllc_a /root/atividade-final-redes-ppgti/.venv/bin/python3 /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_urllc.py 10.0.3.2 5000 0.5 60 &
```

### Iniciar tráfego eMBB manualmente
Servidor em h_embb_b:
```bash
h_embb_b /root/atividade-final-redes-ppgti/.venv/bin/python3 /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py servidor &
```

Cliente em h_embb_a:
```bash
h_embb_a /root/atividade-final-redes-ppgti/.venv/bin/python3 /root/atividade-final-redes-ppgti/etapa3_solucao/gerador_embb.py cliente 10.0.4.2 5001 60 3M udp &
```

### Gerar gráfico a partir de resultados salvos
```bash
/root/atividade-final-redes-ppgti/.venv/bin/python3 etapa3_solucao/coletar_resultados.py /tmp/latencias_urllc.csv /tmp/grafico_latencias.png /tmp/eventos_controle.txt
```

### Limpar ambiente Mininet
```bash
sudo mn -c
```

---

## Desafios encontrados e aprendizados

1. **Checksum offload**: os pacotes TCP/UDP enviados pelos hosts tinham checksum placeholder devido ao offload da NIC virtual. O destinatário descartava os pacotes. A solução foi desabilitar o checksum offload nas interfaces dos hosts.

2. **Opções TCP**: extrair o cabeçalho TCP completo em P4 é complexo porque o TCP tem opções de tamanho variável. A solução foi usar `packet.lookahead` para ler apenas as portas sem modificar o cabeçalho.

3. **Namespaces de rede e Thrift**: o monitor roda dentro do namespace do host `h_urllc_b` e não consegue acessar as portas Thrift dos roteadores. A solução foi usar sinalização por arquivo, com o atuador rodando no namespace raiz.

4. **Latência base alta**: a topologia com 4 saltos e delays de 2 ms por link já gera latência base acima de 5 ms. O limiar de 5 ms é atingido rapidamente, ativando o controle.

5. **Congestionamento realista**: para observar o efeito do controle, a taxa do eMBB foi ajustada para 5 Mbps em links de 10 Mbps.

---

## Possíveis melhorias futuras

- Implementar filas de prioridade reais no BMv2 (requer configuração do traffic manager).
- Usar P4Runtime em vez de Thrift para inserção de regras.
- Adicionar um segundo caminho entre roteadores para permitir redirecionamento de tráfego uRLLC.
- Implementar um protocolo ARP mínimo no switch P4 para evitar entradas estáticas.
- Usar Scapy para geração e captura de pacotes uRLLC, como alternativa aos sockets.
