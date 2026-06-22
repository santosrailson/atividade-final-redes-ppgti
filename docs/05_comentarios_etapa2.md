# Comentários da Etapa 2 — Switches Simples em P4

Este documento explica cada arquivo e cada decisão tomada na Etapa 2. O objetivo é complementar os códigos, que não possuem comentários inline.

---

## Arquivo: `etapa2_p4_basico/instalar_bmv2_p4c.sh`

Esse script instala o compilador P4 (`p4c`) e o switch de software BMv2 a partir de imagens Docker pré-compiladas. A compilação dessas ferramentas do código-fonte pode levar horas e exigir muitos recursos, por isso optamos por extrair os binários já compilados dos containers oficiais do p4lang.

### `DIRETORIO_PROJETO`
Determina o caminho absoluto da raiz do projeto, subindo um nível a partir do diretório onde o script está.

### `DIRETORIO_LIBS`
Define o caminho onde as bibliotecas compartilhadas necessárias ao BMv2 serão armazenadas.

### `verificar_docker()`
Verifica se o Docker está instalado no sistema. Sem Docker, não é possível baixar as imagens pré-compiladas.

### `baixar_imagens()`
Faz o download das imagens `p4lang/p4c` e `p4lang/behavioral-model` do Docker Hub.

### `copiar_binarios()`
Cria containers temporários a partir das imagens baixadas, sem iniciá-los. Em seguida, copia os executáveis do container para `/usr/local/bin` do host:
- Do container `p4lang/p4c`: `p4c`, `p4c-bm2-ss`, `p4c-graphs`.
- Do container `p4lang/behavioral-model`: `simple_switch`, `simple_switch_grpc`, `simple_switch_CLI`.

### `copiar_bibliotecas()`
Copia as bibliotecas compartilhadas das quais os executáveis do BMv2 dependem. Essas bibliotecas são de versões específicas do Ubuntu usado nos containers e podem não existir no Debian 13 do host. As libs copiadas incluem:
- `libjsoncpp`
- `libboost_program_options` e `libboost_iostreams`
- `libssl` e `libcrypto` (OpenSSL 1.1)
- `libev`
- `libpcre`
- `libavl`

### `configurar_ambiente()`
Exibe uma mensagem informando que a variável `LD_LIBRARY_PATH` deve ser configurada para que o sistema encontre as bibliotecas copiadas.

### `verificar_instalacao()`
Configura o `LD_LIBRARY_PATH` temporariamente e executa os comandos `p4c --version`, `simple_switch_grpc --version` e `simple_switch --version` para confirmar que tudo funciona.

---

## Arquivo: `etapa2_p4_basico/compilar_e_executar.sh`

Esse script automatiza a compilação do programa P4 e permite iniciar o switch manualmente fora do Mininet, se desejado.

### `DIRETORIO_PROJETO`
Caminho absoluto da raiz do projeto.

### `export LD_LIBRARY_PATH=...`
Configura o caminho das bibliotecas do BMv2 para a sessão atual do script.

### `compilar()`
Remove o diretório de saída anterior, cria um novo e executa o `p4c`:
```bash
p4c --target bmv2 --arch v1model --std p4-16 programa.p4 -o diretorio_saida
```

O `p4c` cria um subdiretório com o mesmo nome do arquivo P4 dentro do diretório de saída. O JSON compilado fica em:
```
etapa2_p4_basico/compilado/encaminhamento_basico.json/encaminhamento_basico.json
```

### `executar_switch()`
Inicia o `simple_switch_grpc` com as interfaces de rede especificadas. Esse bloco é útil para testes manuais, mas na prática a topologia do Mininet inicia o switch automaticamente.

### `case`
Permite escolher entre compilar, executar ou ambos. Se nenhum argumento for passado, o script compila e executa.

---

## Arquivo: `etapa2_p4_basico/encaminhamento_basico.p4`

Esse é o primeiro programa P4 do projeto. Ele implementa encaminhamento IPv4 básico em um switch BMv2 usando a arquitetura v1model.

### `#include <core.p4>` e `#include <v1model.p4>`
Incluem as definições da linguagem P4 e da arquitetura v1model. Sem esses arquivos, o programa não conheceria tipos como `packet_in`, `packet_out` e `standard_metadata_t`.

### `header ethernet_t`
Define o cabeçalho Ethernet com três campos:
- `endereco_destino`: 48 bits (MAC de destino).
- `endereco_origem`: 48 bits (MAC de origem).
- `tipo_ethernet`: 16 bits (identifica o protocolo da camada superior, como IPv4 = 0x0800).

### `header ipv4_t`
Define o cabeçalho IPv4 com todos os campos padrão, incluindo endereços de origem e destino, TTL, protocolo e checksum.

### `struct headers`
Agrupa os cabeçalhos que serão extraídos do pacote.

### `struct metadata`
Estrutura vazia de metadados. Neste programa simples, não precisamos de metadados extras.

### `parser ParserEntrada`
Extrai os cabeçalhos do pacote:
- No estado `start`, extrai o cabeçalho Ethernet.
- Verifica o campo `tipo_ethernet`.
- Se for `0x0800` (IPv4), transita para o estado `parse_ipv4`.
- Caso contrário, aceita o pacote com apenas o Ethernet extraído.
- No estado `parse_ipv4`, extrai o cabeçalho IPv4.

### `control VerificarChecksum`
Controle vazio. A verificação de checksum pode ser implementada aqui, mas não é necessária para o encaminhamento básico.

### `control Ingresso`
Controle principal de processamento de entrada.

#### `action descartar()`
Marca o pacote para descarte usando `mark_to_drop`.

#### `action encaminhar_ipv4(...)`
Define a porta de saída, atualiza os endereços MAC e decrementa o TTL:
- `metadados_padrao.egress_spec = porta_saida`: indica para qual porta o pacote deve sair.
- `hdr.ethernet.endereco_origem = hdr.ethernet.endereco_destino`: o MAC de origem passa a ser o antigo MAC de destino.
- `hdr.ethernet.endereco_destino = endereco_mac_destino`: define o novo MAC de destino.
- `hdr.ipv4.ttl = hdr.ipv4.ttl - 1`: decrementa o TTL.

#### `table tabela_ipv4_lpm`
Tabela de encaminhamento IPv4 usando correspondência LPM (Longest Prefix Match) no endereço de destino.

#### `apply`
Se o cabeçalho IPv4 for válido, aplica a tabela de encaminhamento. Caso contrário, o pacote segue sem modificação e é descartado pela ação padrão se não houver correspondência.

### `control Egresso`
Controle de saída vazio. Poderia ser usado para processamento adicional antes do pacote sair.

### `control CalcularChecksum`
Recalcula o checksum do cabeçalho IPv4 após o decremento do TTL. A função `update_checksum` recebe:
- Uma condição de validade.
- A lista de campos que participam do cálculo.
- O campo onde o resultado será armazenado.
- O algoritmo de checksum (`csum16`).

### `control DeparserSaida`
Remonta o pacote, emitindo os cabeçalhos Ethernet e IPv4. O `emit` só inclui cabeçalhos válidos.

### `V1Switch(...)`
Instancia o switch v1model conectando todos os controles e o parser na ordem esperada pela arquitetura.

---

## Arquivo: `etapa2_p4_basico/topologia_p4.py`

Esse script cria uma topologia Mininet com dois hosts e um switch P4, e testa a conectividade entre eles.

### `DIRETORIO_PROJETO`
Calcula o caminho absoluto da raiz do projeto.

### `CAMINHO_JSON`
Caminho para o arquivo JSON compilado do programa P4.

### `CAMINHO_LIBS`
Caminho para as bibliotecas compartilhadas do BMv2.

### `class SwitchP4(Host)`
Classe customizada que transforma um host do Mininet em um switch P4.

#### Herança de `Host`
Em vez de herdar de `Switch`, herdamos de `Host` porque o BMv2 precisa rodar como um processo comum dentro de um namespace de rede, e a classe `Host` fornece isso de forma simples.

#### `__init__`
Armazena o caminho do JSON e as portas Thrift/gRPC.

#### `start`
Constrói o comando para executar o `simple_switch`:
- Uma opção `-i <porta>@<interface>` para cada interface do switch.
- `--thrift-port`: porta para comunicação com a CLI.
- `--device-id`: identificador do dispositivo.
- `--log-console`: ativa logs no console.
- O caminho do JSON compilado.

O comando é executado com `self.popen`, herdado da classe `Host`. O ambiente inclui o `LD_LIBRARY_PATH` para encontrar as bibliotecas.

#### `stop`
Encerra o processo do switch ao parar a rede.

#### `dpctl`
Executa comandos no `simple_switch_CLI`, passando o comando via stdin e retornando a saída.

### `criar_topologia()`
Monta a rede:
- Cria dois hosts com endereços IP e MAC fixos.
- Cria um switch P4 chamado `s1`.
- Conecta os hosts ao switch.
- Inicia a rede.
- Desabilita IPv6 nos hosts.
- Insere regras de encaminhamento via Thrift.
- Configura entradas ARP estáticas para evitar que pacotes ARP sejam descartados pelo switch.
- Executa ping IPv4 entre os hosts.
- Abre a CLI do Mininet.

### Desabilitando IPv6
O Linux moderno tenta usar IPv6 para resolução de nomes e descoberta de vizinhos. Como o programa P4 só reconhece IPv4, pacotes IPv6 seriam descartados. O script desabilita IPv6 em todas as interfaces dos hosts.

### Entradas ARP estáticas
O protocolo ARP (que resolve IP para MAC) usa o tipo Ethernet `0x0806`. Como o parser do programa P4 só trata IPv4 (`0x0800`), pacotes ARP são descartados. Para que o ping funcione sem precisar implementar ARP no switch, configuramos entradas ARP estáticas nos hosts.

### Números de porta do switch
As interfaces são numeradas a partir de 0 na ordem em que aparecem no comando `-i`. A primeira interface (`s1-eth0`) é a porta 0 e a segunda (`s1-eth1`) é a porta 1. As regras de encaminhamento devem usar esses números.

---

## Arquivo: `etapa2_p4_basico/inserir_regras.py`

Script auxiliar para inserir regras na tabela `tabela_ipv4_lpm` do switch P4 via `simple_switch_CLI`.

### `DIRETORIO_PROJETO` e `CAMINHO_LIBS`
Mesmas definições dos outros scripts.

### `REGRAS`
String contendo os comandos da CLI do BMv2 para adicionar entradas na tabela.

A sintaxe do comando é:
```
table_add <nome_da_tabela> <nome_da_acao> <chave> => <parametros_da_acao>
```

No nosso caso:
```
table_add tabela_ipv4_lpm encaminhar_ipv4 10.0.0.1/32 => 00:00:00:00:00:01 0
```

Isso significa: pacotes destinados a `10.0.0.1/32` devem ser encaminhados usando a ação `encaminhar_ipv4` com MAC de destino `00:00:00:00:00:01` e porta de saída `0`.

### `executar_cli()`
Inicia o `simple_switch_CLI` com comunicação via stdin, envia as regras e exibe a saída.

---

## Comandos manuais da Etapa 2

### Instalar BMv2 e p4c
```bash
bash etapa2_p4_basico/instalar_bmv2_p4c.sh
```

### Configurar LD_LIBRARY_PATH
```bash
export LD_LIBRARY_PATH=/root/atividade-final-redes-ppgti/.p4libs/x86_64-linux-gnu:/root/atividade-final-redes-ppgti/.p4libs/usr_lib:$LD_LIBRARY_PATH
```

Dica: adicione a linha acima ao `~/.bashrc` para não precisar digitá-la sempre.

### Compilar o programa P4
```bash
p4c --target bmv2 --arch v1model --std p4-16 etapa2_p4_basico/encaminhamento_basico.p4 -o etapa2_p4_basico/compilado/encaminhamento_basico.json
```

### Executar a topologia com switch P4
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa2_p4_basico/topologia_p4.py
```

Dentro da CLI do Mininet, você pode testar:
```
pingall
host_a ping -c 4 host_b
exit
```

### Inserir regras manualmente em um switch P4
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa2_p4_basico/inserir_regras.py 9090
```

### Limpar ambiente Mininet
```bash
sudo mn -c
```

---

## Desafios encontrados e aprendizados

1. **Dependências do BMv2**: os binários extraídos dos containers Docker dependem de bibliotecas específicas que não existem no Debian 13. A solução foi copiar essas bibliotecas para um diretório local e configurar `LD_LIBRARY_PATH`.

2. **Argumentos do `simple_switch_grpc`**: a primeira tentativa usou argumentos na ordem errada, fazendo o switch interpretar `--grpc-server-addr` como arquivo JSON. A correção foi simplificar o comando e usar `simple_switch` (sem gRPC), que é suficiente para comunicação via Thrift.

3. **IPv6 no Mininet**: os hosts do Mininet geram tráfego IPv6 automaticamente. Como o parser P4 só reconhece IPv4, esses pacotes eram descartados. A solução foi desabilitar IPv6 nos hosts.

4. **ARP não implementado**: o switch P4 descarta pacotes ARP porque não os reconhece. Para o teste introdutório, usamos entradas ARP estáticas. Na Etapa 3, podemos optar por implementar ARP no switch ou manter a abordagem estática.

5. **Números de porta**: as portas do BMv2 começam em 0 e seguem a ordem das opções `-i`. Usar 1 e 2 inicialmente fez com que os pacotes fossem encaminhados para interfaces inexistentes.

---

## Próximos passos

Na Etapa 3, o programa P4 será estendido para:
- Classificar tráfego uRLLC e eMBB.
- Implementar filas de prioridade.
- Permitir que o controlador Python reconfigure regras em tempo real para garantir a latência de 5 ms.
