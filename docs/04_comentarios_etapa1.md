# Comentários da Etapa 1 — Ambiente Mininet + Python

Este documento explica linha a linha, ou bloco a bloco, o que cada script da Etapa 1 faz. O objetivo é complementar os arquivos de código, que não possuem comentários inline.

---

## Arquivo: `etapa1_ambiente/instalar_dependencias.sh`

Esse script automatiza a instalação de tudo o que é necessário para executar o projeto.

### `#!/bin/bash`
Indica que o arquivo deve ser interpretado pelo shell Bash.

### `atualizar_repositorios()`
Atualiza a lista de pacotes disponíveis no sistema com `apt-get update`.

### `instalar_mininet()`
Instala o Mininet e o Open vSwitch, que é o switch de software usado por padrão.

### `instalar_ferramentas_trafego()`
Instala o `iperf3` e o `ffmpeg`, usados na Etapa 3 para gerar tráfego eMBB.

### `instalar_python_e_venv()`
Instala o Python 3, o módulo de ambientes virtuais e o pip.

### `criar_ambiente_virtual()`
Remove o ambiente virtual anterior, se existir, e cria um novo com a flag `--system-site-packages`. Essa flag é importante porque permite que o ambiente virtual acesse o Mininet instalado no sistema operacional, já que o Mininet geralmente não é instalado via pip.

### `instalar_bibliotecas_python()`
Ativa o ambiente virtual e instala as bibliotecas Python: Scapy, Matplotlib e Pandas.

### `verificar_instalacao()`
Ativa o ambiente virtual e executa um pequeno script Python que tenta importar cada biblioteca. Em seguida, executa `mn --test pingall`, que cria uma rede mínima no Mininet e testa a conectividade.

### Chamadas finais
As funções são chamadas em sequência: atualização, instalação do Python, instalação do Mininet, instalação das ferramentas de tráfego, criação do ambiente virtual, instalação das bibliotecas e verificação.

---

## Arquivo: `etapa1_ambiente/topologia_simples.py`

Esse script cria uma rede Mininet com dois hosts e um switch, e abre a interface interativa para exploração manual.

### `from mininet.net import Mininet`
Importa a classe principal que representa a rede emulada.

### `from mininet.node import OVSController`
Importa a classe do controlador embutido no Open vSwitch, usado como alternativa ao controlador de referência OpenFlow.

### `from mininet.link import TCLink`
Importa a classe de link com controle de tráfego.

### `from mininet.cli import CLI`
Importa a interface interativa do Mininet.

### `from mininet.log import setLogLevel, info`
Importa funções para configurar logs e exibir mensagens.

### `def criar_topologia():`
Define a função principal que monta e executa a rede.

### `rede = Mininet(controller=OVSController, link=TCLink)`
Cria o objeto rede, informando que será usado o controlador do Open vSwitch e links com controle de tráfego.

### `controlador = rede.addController("c0")`
Adiciona um controlador à rede. O nome `"c0"` é apenas um identificador.

### `host_a = rede.addHost("host_a", ip="10.0.0.1/24")`
Cria o host A com endereço IP 10.0.0.1 e máscara de rede /24.

### `host_b = rede.addHost("host_b", ip="10.0.0.2/24")`
Cria o host B com endereço IP 10.0.0.2.

### `switch = rede.addSwitch("s1")`
Cria um switch chamado s1.

### `rede.addLink(host_a, switch, bw=100)`
Conecta o host A ao switch com largura de banda de 100 Mbps.

### `rede.addLink(host_b, switch, bw=100)`
Conecta o host B ao switch.

### `rede.start()`
Inicia a rede: configura as interfaces virtuais, atribui IPs e inicializa o switch e o controlador.

### `rede.pingAll()`
Executa ping entre todos os pares de hosts para verificar conectividade.

### `CLI(rede)`
Abre a interface interativa do Mininet, permitindo que o usuário execute comandos manualmente.

### `rede.stop()`
Encerra a rede e remove as configurações criadas.

### `if __name__ == "__main__":`
Garante que a função `criar_topologia()` só seja executada quando o arquivo for rodado diretamente.

### `setLogLevel("info")`
Configura o nível de log para exibir mensagens informativas.

---

## Arquivo: `etapa1_ambiente/teste_ping.py`

Esse script automatiza um teste simples de ping entre dois hosts, sem abrir a CLI interativa.

### Importações
As mesmas importações do script anterior, exceto a `CLI`, que não é usada aqui.

### `def executar_teste_ping():`
Define a função principal do teste.

### Criação da rede
As mesmas etapas de criação de controlador, hosts, switch e links.

### `rede.start()`
Inicia a rede.

### `resultado = host_a.cmd("ping -c 4 10.0.0.2")`
Executa o comando `ping -c 4 10.0.0.2` dentro do namespace de rede do host A. O parâmetro `-c 4` envia quatro pacotes ICMP. O resultado é armazenado na variável `resultado`.

### `info(resultado)`
Exibe a saída do comando ping na tela.

### `rede.stop()`
Encerra a rede.

---

## Arquivo: `etapa1_ambiente/teste_latencia_scapy.py`

Esse script mede a latência entre dois hosts usando uma combinação de socket TCP puro no servidor e Scapy no cliente.

### Importações iniciais
As mesmas do Mininet, mais `import time` para medição de tempo.

### `def executar_teste_latencia():`
Define a função principal.

### Criação da rede
Cria os mesmos dois hosts, switch e links dos scripts anteriores.

### `host_b.cmd(comando_servidor)`
Inicia um servidor TCP em segundo plano no host B. O comando é um here-document, ou seja, um bloco de código Python passado diretamente para o interpretador. A saída é redirecionada para `/tmp/servidor.log` e o processo roda em background graças ao `&`.

### Servidor TCP em detalhe
- `servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)`: cria um socket TCP IPv4.
- `servidor.bind(("0.0.0.0", 8000))`: associa o socket a todas as interfaces na porta 8000.
- `servidor.listen(1)`: coloca o socket em modo de escuta.
- `servidor.accept()`: aguarda uma conexão.
- `conexao.recv(1024)`: recebe até 1024 bytes.
- `conexao.sendall(dados)`: devolve os dados recebidos de volta ao cliente.
- `conexao.close()`: fecha a conexão.

### `time.sleep(1)`
Pausa a execução por um segundo para garantir que o servidor já esteja ativo antes do cliente tentar conectar.

### Script Scapy do cliente
Outro here-document é executado no host A, mas usando o caminho absoluto do interpretador Python do ambiente virtual (`/root/atividade-final-redes-ppgti/.venv/bin/python3`). Isso é necessário porque, dentro do namespace de rede de cada host do Mininet, o ambiente virtual não está ativado por padrão. Usando o caminho absoluto, garantimos que o Scapy instalado no ambiente virtual esteja disponível.

Esse bloco:
- Desativa os logs detalhados do Scapy com `conf.verb = 0`.
- Registra o tempo atual em `inicio`.
- Constrói um pacote TCP SYN para o destino 10.0.0.2 na porta 8000.
- Envia o pacote e aguarda uma única resposta com `sr1`.
- Registra o tempo atual em `fim`.
- Se houver resposta, calcula a latência em milissegundos.
- Se não houver resposta, exibe uma mensagem de erro.

### `info(resultado)`
Exibe a latência medida na tela.

### `rede.stop()`
Encerra a rede.

---

## Observações gerais da Etapa 1

- Os scripts usam o `OVSController`, controlador embutido no Open vSwitch, que já aprende automaticamente os endereços MAC e encaminha pacotes entre hosts da mesma sub-rede.
- A latência medida com Scapy representa o tempo de ida e volta do handshake TCP (SYN e SYN-ACK). Na prática, o valor pode ser muito baixo porque os hosts estão no mesmo sistema, mas serve como introdução à técnica.
- O uso de `host.cmd()` é fundamental para automatizar experimentos no Mininet sem interação manual.

---

## Comandos manuais da Etapa 1

Todos os comandos a seguir assumem que o ambiente virtual está ativado ou que você usa o caminho absoluto do Python do ambiente virtual.

### Instalar dependências
```bash
bash etapa1_ambiente/instalar_dependencias.sh
```

### Ativar ambiente virtual
```bash
source .venv/bin/activate
```

### Executar topologia simples (abre CLI do Mininet)
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/topologia_simples.py
```

Dentro da CLI do Mininet, comandos úteis:
```
nodes
links
pingall
host_a ping -c 4 host_b
exit
```

### Executar teste de ping automatizado
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/teste_ping.py
```

### Executar teste de latência com Scapy
```bash
sudo /root/atividade-final-redes-ppgti/.venv/bin/python3 etapa1_ambiente/teste_latencia_scapy.py
```

### Limpar ambiente Mininet (em caso de erro ou travamento)
```bash
sudo mn -c
```
