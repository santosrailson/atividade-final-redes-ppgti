# Fundamentos do Mininet

Este documento explica o que é o Mininet, como ele funciona internamente, quais são seus principais componentes e como usá-lo através da API Python e da linha de comando.

## 1. O que é o Mininet

Mininet é um emulador de redes de computadores. Ele cria uma rede virtual completa — com hosts, switches, roteadores, controladores e links — executando todos os elementos como processos dentro de um único sistema operacional Linux.

A principal vantagem do Mininet é permitir testar protocolos, aplicações e arquiteturas de rede sem precisar de equipamentos físicos.

## 2. Arquitetura do Mininet

O Mininet utiliza recursos do kernel Linux para isolar processos e interfaces de rede:

- **Namespaces de rede**: cada host do Mininet roda em seu próprio namespace de rede, com suas próprias interfaces, tabelas de roteamento e regras de firewall.
- **Interfaces virtuais (veth pairs)**: pares de interfaces virtuais conectadas entre si formam os links da rede emulada.
- **Open vSwitch**: switch de software usado como switch padrão no Mininet para encaminhar pacotes entre hosts.
- **Controlador SDN**: em cenários com OpenFlow, o controlador gerencia as tabelas de fluxo dos switches.

## 3. Componentes principais

### Host

Representa um computador final na rede. Cada host tem seu próprio endereço IP, interface de rede e namespace isolado. Nos scripts, hosts são criados com `rede.addHost()`.

### Switch

Representa um switch de rede. O Mininet usa o Open vSwitch por padrão. Switches são criados com `rede.addSwitch()`.

### Controlador

Representa o controlador da rede. Em redes OpenFlow, o controlador é responsável por preencher as tabelas de encaminhamento dos switches.

Neste projeto, usamos o `OVSController`, que é um controlador de teste embutido no Open vSwitch. Ele é suficiente para topologias simples onde o encaminhamento L2 entre hosts da mesma sub-rede precisa ser resolvido automaticamente.

A classe `Controller` do Mininet exige a instalação do controlador de referência OpenFlow, que nem sempre está disponível nos repositórios modernos. Por isso, optamos pelo `OVSController`, instalado através do pacote `openvswitch-testcontroller`.

### Link

Representa a conexão entre dois elementos da rede. No Mininet, links podem ser configurados com largura de banda, atraso e taxa de perda. A classe `TCLink` permite essa configuração usando o `tc` (traffic control) do Linux.

## 4. API Python do Mininet

### Classe Mininet

A classe `Mininet` é o ponto central da API. Ela representa a rede emulada e permite criar, conectar, iniciar e parar os elementos.

Principais métodos:
- `addHost(nome, ip=...)`: cria um novo host.
- `addSwitch(nome)`: cria um novo switch.
- `addController(nome)`: cria um controlador.
- `addLink(no1, no2, bw=..., delay=..., loss=...)`: conecta dois nós.
- `start()`: inicia a rede, configurando interfaces e controladores.
- `stop()`: encerra a rede e remove as configurações.
- `pingAll()`: executa ping entre todos os pares de hosts.

### Classe Topo

A classe `Topo` permite definir topologias de forma declarativa. Embora os scripts da Etapa 1 criem a rede diretamente com a classe `Mininet`, em projetos maiores é comum usar `Topo` para separar a descrição da topologia da lógica de execução.

### TCLink

A classe `TCLink` cria links com controle de tráfego. É possível especificar:
- `bw`: largura de banda em Mbps.
- `delay`: atraso de propagação, por exemplo `"10ms"`.
- `loss`: taxa de perda de pacotes em porcentagem.

### CLI

A classe `CLI` abre uma interface interativa que permite executar comandos dentro dos hosts e switches. É útil para depuração e exploração manual da rede.

## 5. Comandos da linha de comando do Mininet

Além da API Python, o Mininet oferece uma CLI interativa com vários comandos úteis:

- `nodes`: lista todos os nós da rede.
- `links`: mostra o estado dos links.
- `dump`: exibe informações detalhadas sobre hosts, switches e controladores.
- `pingall`: executa ping entre todos os pares de hosts.
- `pingpair`: executa ping entre o primeiro e o último host.
- `iperf`: executa teste de largura de banda entre dois hosts.
- `xterm host_a`: abre um terminal gráfico para o host especificado.
- `host_a comando`: executa um comando no host, por exemplo `host_a ping -c 4 host_b`.
- `exit` ou `quit`: encerra o Mininet.

## 6. Fluxo de execução de um script Mininet

Um script típico do Mininet segue os seguintes passos:

1. **Criar o objeto rede**: `rede = Mininet(...)`.
2. **Adicionar o controlador**: `rede.addController(...)`.
3. **Adicionar hosts e switches**: `rede.addHost(...)`, `rede.addSwitch(...)`.
4. **Conectar os elementos**: `rede.addLink(...)`.
5. **Iniciar a rede**: `rede.start()`.
6. **Executar testes ou abrir a CLI**.
7. **Parar a rede**: `rede.stop()`.

## 7. Log e mensagens

A função `setLogLevel("info")` configura o nível de detalhamento das mensagens do Mininet. Os níveis comuns são:
- `debug`: mensagens muito detalhadas.
- `info`: mensagens informativas padrão.
- `warning`: apenas avisos e erros.
- `error`: apenas erros.

A função `info(...)` exibe mensagens na tela durante a execução do script.

## 8. Limitações importantes

- O Mininet emula a rede no espaço do usuário e compartilha a CPU com outros processos. Por isso, comportamentos de temporização podem não ser perfeitamente precisos.
- A precisão das medições de latência depende da carga do sistema e da granularidade do escalonador do Linux.
- Para resultados mais realistas, é recomendável executar experimentos várias vezes e calcular médias.

## 9. Relação com o projeto

Neste projeto, o Mininet é usado para emular a rede de transporte 5G com quatro switches OVS em linha. Os hosts geram tráfego uRLLC e eMBB, e os switches executam regras OpenFlow e filas QoS/HTB para classificar e priorizar o tráfego.

O domínio da API Python do Mininet é essencial para automatizar a criação da topologia, a execução de testes e a coleta de métricas.
