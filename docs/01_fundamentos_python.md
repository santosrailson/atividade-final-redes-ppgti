# Fundamentos de Python para o Projeto

Este documento apresenta os conceitos de Python utilizados nos scripts da Etapa 1. O foco é entender o que cada função e estrutura faz, sem aprofundar em aspectos avançados da linguagem.

## 1. O que é Python

Python é uma linguagem de programação interpretada, de alto nível e com sintaxe simples. Isso significa que o código escrito em Python é lido linha a linha por um programa chamado interpretador, que executa as instruções sem precisar compilar previamente para código de máquina.

Neste projeto, Python é usado para duas finalidades principais:
- Construir e controlar topologias de rede no Mininet.
- Gerar, capturar e analisar pacotes de rede com a biblioteca Scapy.

## 2. Variáveis e tipos de dados

Uma variável é um nome que armazena um valor na memória. Em Python, não é necessário declarar o tipo da variável antecipadamente.

Exemplos usados nos scripts:
- `rede = Mininet(...)`: armazena o objeto que representa a rede emulada.
- `host_a = rede.addHost(...)`: armazena o objeto que representa o host A.
- `resultado = host_a.cmd(...)`: armazena a saída de texto do comando executado.

Tipos comuns encontrados:
- `str`: texto, como `"host_a"` ou `"10.0.0.1/24"`.
- `int`: números inteiros, como a quantidade de pacotes enviados no ping.
- `float`: números decimais, como o valor de tempo retornado por `time.time()`.
- `bool`: valores verdadeiro (`True`) ou falso (`False`).

## 3. Funções

Uma função é um bloco de código reutilizável que realiza uma tarefa. Em Python, funções são definidas com a palavra `def`.

Nos scripts da Etapa 1, a função principal é `criar_topologia()` ou `executar_teste_ping()`. Essa função agrupa todas as instruções necessárias para montar a rede e realizar o experimento.

A linha `if __name__ == "__main__":` garante que o código dentro dela só seja executado quando o arquivo é rodado diretamente, e não quando importado por outro arquivo.

## 4. Importação de módulos

Para usar funcionalidades prontas, importamos módulos. Existem três formas comuns:

- `from mininet.net import Mininet`: importa a classe `Mininet` do módulo `mininet.net`.
- `from mininet.node import Controller`: importa a classe `Controller`.
- `from mininet.link import TCLink`: importa a classe `TCLink`, que permite configurar largura de banda, atraso e perda nos links.
- `from mininet.cli import CLI`: importa a interface interativa do Mininet.
- `from mininet.log import setLogLevel, info`: importa funções para configurar o nível de log e exibir mensagens informativas.

A importação `import time` permite usar funções relacionadas ao tempo, como `time.sleep()` para pausar a execução e `time.time()` para obter o timestamp atual.

## 5. Strings e formatação

Strings são sequências de caracteres delimitadas por aspas simples ou duplas. A formatação de strings permite inserir valores dentro de textos.

Exemplos:
- `"Latencia: %.3f ms" % latencia_ms`: formata o número com três casas decimais.
- `"ping -c 4 10.0.0.2"`: string que representa o comando a ser executado.

## 6. Estruturas de controle

### Condicional if

A estrutura `if` permite executar um bloco de código apenas se uma condição for verdadeira.

Exemplo:
```python
if resposta is not None:
    latencia_ms = (fim - inicio) * 1000
else:
    print("Nenhuma resposta recebida")
```

Nesse exemplo, verificamos se a variável `resposta` contém um pacote de resposta. Se contiver, calculamos a latência. Caso contrário, exibimos uma mensagem de erro.

### Laço while

O laço `while` executa um bloco de código enquanto uma condição for verdadeira. No script do servidor TCP, ele é usado para manter o servidor aceitando conexões indefinidamente:

```python
while True:
    conexao, endereco = servidor.accept()
```

## 7. Manipulação de tempo

A função `time.time()` retorna o número de segundos decorridos desde 1º de janeiro de 1970. Esse valor é usado como referência para calcular intervalos de tempo.

Para medir a latência, registramos o tempo antes de enviar o pacote e subtraímos do tempo após receber a resposta:

```python
inicio = time.time()
# envia pacote e espera resposta
fim = time.time()
latencia_ms = (fim - inicio) * 1000
```

A multiplicação por 1000 converte segundos para milissegundos.

## 8. Sockets em Python

Socket é uma interface de programação que permite a comunicação entre processos através da rede. Os sockets são a base da comunicação TCP/IP.

### Servidor TCP

No script de teste de latência, o host B executa um servidor simples:

```python
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.bind(("0.0.0.0", 8000))
servidor.listen(1)
```

- `socket.AF_INET`: indica que será usado o protocolo IPv4.
- `socket.SOCK_STREAM`: indica que será usado o protocolo TCP.
- `bind`: associa o socket a um endereço IP e porta.
- `listen`: coloca o socket em modo de escuta, aguardando conexões.

Quando uma conexão chega:
```python
conexao, endereco = servidor.accept()
dados = conexao.recv(1024)
conexao.sendall(dados)
```

- `accept`: aceita uma nova conexão.
- `recv`: recebe dados do cliente.
- `sendall`: envia os dados de volta ao cliente.

## 9. O módulo Scapy

Scapy é uma biblioteca Python poderosa para construir, enviar, receber e manipular pacotes de rede.

### Construção de pacotes

Em Scapy, pacotes são construídos empilhando camadas com o operador `/`:

```python
pacote = IP(dst="10.0.0.2") / TCP(dport=8000, flags="S")
```

- `IP(dst="10.0.0.2")`: camada de rede IPv4 com endereço de destino.
- `TCP(dport=8000, flags="S")`: camada de transporte TCP com porta de destino 8000 e flag SYN.

### Envio e recepção

A função `sr1` envia um pacote e aguarda uma única resposta:

```python
resposta = sr1(pacote, timeout=2)
```

O parâmetro `timeout=2` indica que o programa espera no máximo 2 segundos por uma resposta. Se nenhuma resposta for recebida, a função retorna `None`.

A configuração `conf.verb = 0` desativa mensagens detalhadas do Scapy durante a execução.

## 10. Execução de comandos nos hosts do Mininet

A API do Mininet permite executar comandos dentro dos hosts emulados:

```python
resultado = host_a.cmd("ping -c 4 10.0.0.2")
```

A função `cmd` executa o comando no namespace de rede do host e retorna a saída como texto. Isso permite automatizar testes sem precisar interagir manualmente com a CLI do Mininet.

## 11. Organização do código

Os scripts da Etapa 1 seguem um padrão comum:
1. Importação dos módulos necessários.
2. Definição de uma função principal que cria a rede e executa o experimento.
3. Chamada da função principal dentro do bloco `if __name__ == "__main__":`.

Essa organização facilita a leitura, a manutenção e a reutilização do código em etapas futuras.
