# Sistema de Monitoramento e Controle Closed Loop uRLLC/eMBB — Versão macOS

Projeto final da disciplina Redes de Computadores (PPGTI). Sistema de
monitoramento e controle em malha fechada (*closed loop*) que garante que
aplicações **uRLLC** não excedam **5 ms** de latência fim-a-fim em uma rede
de transporte 5G emulada, mesmo coexistindo com tráfego **eMBB** de alto
volume.

## Cenário de aplicação: segurança contra incêndio em um campus universitário

O experimento simula uma rede de monitoramento de segurança/incêndio de um
campus universitário com **três prédios** (Biblioteca, Bloco de
Laboratórios e Reitoria), cada um equipado com:

- um **sensor de incêndio/fumaça** (ex.: Arduino + sensor de chama/gás),
  que envia alertas críticos — tráfego **uRLLC** — e que precisa chegar à
  central em, no máximo, **5 ms**, pois um alarme atrasado é inútil;
- uma **câmera de vigilância**, que faz streaming contínuo de vídeo para
  confirmação visual dos alertas — tráfego **eMBB**, de alto volume e
  tolerante a latências maiores.

Os três prédios enviam tráfego simultaneamente, cada um por um switch de
acesso diferente da rede de transporte (backbone de 4 switches OVS,
representando o núcleo da rede do campus), convergindo para uma única
**Central de Monitoramento (NOC)**:

```
sens_bib --\                                          /-- c_urllc
cam_bib  --/-- r1 --\                                  |   (alertas de incêndio)
                     \                                 |
sens_lab --\          r2 ---- r3 ---- r4 --------------+
cam_lab  --/---------/                                 |
                                                        \-- c_video
sens_rei --\                                                (vídeo das câmeras)
cam_rei  --/-------- r3 (acima)
```

Quando o vídeo das câmeras congestiona a rede a ponto de ameaçar o SLA de
5 ms dos alertas de incêndio, o **controlador closed loop** (a mesma lógica
de QoS/OpenFlow já usada no restante do projeto) derruba temporariamente o
tráfego eMBB dos 3 prédios, priorizando os alertas críticos — e libera o
vídeo de volta assim que a latência normaliza. Essa reconfiguração
dinâmica de fatiamento de rede (uRLLC crítico vs. eMBB tolerante) é o que
caracteriza o cenário como uma rede **5G uRLLC/eMBB**, ainda que sensores
reais de campo tipicamente usem tecnologias de acesso como LoRaWAN/Zigbee —
aqui elas são representadas pela conexão uRLLC até a central.

Mapeamento dos hosts Mininet (nomes curtos por limite de 15 caracteres do
Linux para nomes de interface):

| Prédio | Sensor (uRLLC) | Câmera (eMBB) | Switch de acesso |
|---|---|---|---|
| Biblioteca | `sens_bib` | `cam_bib` | `r1` |
| Bloco de Laboratórios | `sens_lab` | `cam_lab` | `r2` |
| Reitoria | `sens_rei` | `cam_rei` | `r3` |
| Central de Monitoramento (NOC) | `c_urllc` | `c_video` | `r4` |

Todo o código-fonte, adaptado para rodar no macOS via Docker, está em
[`solucao_macos/`](solucao_macos/): um ambiente autocontido que reúne
topologia, geração/monitoramento de tráfego, controle e análise estatística
em um único lugar, pronto para gerar os resultados e gráficos usados no
artigo final. **Os comandos abaixo devem ser executados de dentro dessa
pasta** (`cd solucao_macos`).

## Por que Docker no macOS?

O **Mininet** e o **Open vSwitch** dependem de recursos exclusivos do kernel
Linux (namespaces de rede, veth pairs, datapath do OVS) que **não existem no
macOS** (kernel Darwin). Não é possível rodá-los nativamente aqui.

A solução padrão da comunidade Mininet para isso é rodar tudo dentro de um
**container Linux via Docker Desktop for Mac** — o Docker Desktop já mantém
uma VM Linux internamente, então o container roda um kernel Linux de
verdade, e o Mininet funciona normalmente dentro dele. A pasta
`solucao_macos/` traz um `Dockerfile` pronto para isso.

> O Open vSwitch é configurado para usar o **datapath em userspace**
> (`datapath="user"` / `datapath_type=netdev`), que não exige o módulo de
> kernel `openvswitch.ko` — módulo que a VM interna do Docker Desktop
> normalmente não carrega. As regras de QoS/HTB continuam funcionando
> normalmente, pois atuam via `tc` diretamente nas interfaces de rede, e não
> dependem do tipo de datapath do OVS.

## Pré-requisitos

1. **Docker Desktop for Mac** instalado e em execução (Apple Silicon ou
   Intel). Baixe em https://www.docker.com/products/docker-desktop/ caso
   ainda não tenha.
2. Nenhuma outra dependência precisa ser instalada no macOS — Mininet, OVS,
   Python, Scapy, iperf3, pandas, matplotlib e scipy ficam todos dentro da
   imagem Docker.

## Estrutura do repositório

```
.
├── README.md                           # este arquivo
└── solucao_macos/
    ├── Dockerfile                      # Imagem Linux (Ubuntu 22.04) com Mininet + OVS + Python
    ├── docker-compose.yml              # Sobe o container privilegiado com um comando
    ├── entrypoint.sh                   # Inicializa o Open vSwitch dentro do container
    ├── requirements.txt                # Dependências Python (scapy, pandas, numpy, matplotlib, scipy)
    ├── patch_mininet_r2q.py            # Corrige aviso de kernel do HTB (aplicado no build)
    ├── patch_mininet_fixlimits.py      # Corrige aviso de limites de recursos (aplicado no build)
    ├── topologia.py                    # Topologia Mininet: 4 switches OVS em linha + 3 prédios do campus + central
    ├── experimento.py                  # Orquestrador do experimento (closed loop completo, 3 sites em paralelo)
    ├── gerador_urllc.py                # Gerador de tráfego uRLLC via Scapy/TCP (sensor de incêndio)
    ├── monitor_controlador.py          # Monitor de latência (multi-conexão) + controlador closed loop
    ├── gerador_embb.py                 # Gerador/servidor de tráfego eMBB via iperf3 (câmera de vigilância)
    ├── analisar_resultados.py          # Estatísticas + gráficos de UM experimento
    ├── comparar_cenarios.py            # Estatísticas + gráficos comparando VÁRIOS experimentos
    ├── executar_bateria_testes.sh      # Roda os 4 cenários padrão e já compara no final
    └── resultados/                     # CSVs, gráficos (.png) e resumos (.txt) gerados
```

## Passo a passo

### 1. Construir a imagem

No Terminal, a partir da raiz do repositório:

```bash
cd solucao_macos
docker compose build
```

### 2. Subir o container e abrir um shell

```bash
docker compose run --rm urllc-lab
```

Isso abre um shell **dentro** do container Linux, já como `root` (necessário
para o Mininet criar namespaces de rede) e com o Open vSwitch já iniciado
pelo `entrypoint.sh`. Os comandos das próximas seções devem ser executados
**dentro desse shell**.

A pasta `resultados/` é montada como volume: tudo que for salvo ali dentro
do container aparece automaticamente na pasta `solucao_macos/resultados/`
no seu Mac, pronto para anexar ao artigo.

### 3. Rodar um experimento único

```bash
python3 experimento.py --duracao 60 --taxa-embb 5M --tipo-embb udp --controle reativo --intervalo-urllc 0.1
```

Principais parâmetros de `experimento.py`:

| Parâmetro | Significado | Padrão |
|---|---|---|
| `--duracao` | Duração do experimento em segundos | `60` |
| `--taxa-embb` | Taxa de bits do tráfego eMBB (ex.: `5M`, `10M`) | `5M` |
| `--tipo-embb` | Protocolo do eMBB (`udp` ou `tcp`) | `udp` |
| `--controle` | `nenhum`, `preventivo` (dropa eMBB desde o início) ou `reativo` (só dropa ao violar 5 ms) | `reativo` |
| `--sem-embb` | Roda uRLLC isolado, sem tráfego eMBB concorrente | desligado |
| `--intervalo-urllc` | Intervalo entre pacotes uRLLC, em segundos | `0.1` |

Ao final, o script já chama `analisar_resultados.py` automaticamente e
imprime o resumo estatístico no terminal, além de salvar os gráficos em
`resultados/`.

### 4. Rodar a bateria de testes completa (recomendado para o artigo)

Executa 4 cenários em sequência — uRLLC isolado, uRLLC+eMBB sem controle,
com controle preventivo e com controle reativo — e já gera a comparação
estatística entre eles:

```bash
./executar_bateria_testes.sh
```

Ou, direto do macOS sem precisar abrir o shell manualmente:

```bash
docker compose run --rm urllc-lab ./executar_bateria_testes.sh
```

Parâmetros ajustáveis via variável de ambiente:

```bash
DURACAO=90 TAXA_EMBB=10M ./executar_bateria_testes.sh
```

### 5. Rodar a topologia interativamente (opcional, para inspeção manual)

```bash
python3 topologia.py
```

Abre a CLI do Mininet (`mininet>`) com a topologia de pé, útil para testar
conectividade manualmente (`sens_bib ping c_urllc`) ou inspecionar as
regras OpenFlow (`sh ovs-ofctl -O OpenFlow13 dump-flows r1`).

## Como gerar as imagens estatísticas

### Para um experimento isolado

`analisar_resultados.py` é chamado automaticamente ao final de
`experimento.py`, mas também pode ser rodado manualmente sobre qualquer CSV
de latências:

```bash
python3 analisar_resultados.py resultados/latencias_urllc.csv resultados/eventos_controle.txt resultados/ --sufixo meu_teste
```

Isso gera, na pasta `resultados/`:

- `resumo_estatistico_meu_teste.txt` — estatísticas descritivas.
- `grafico_serie_temporal_meu_teste.png`
- `grafico_histograma_meu_teste.png`
- `grafico_boxplot_meu_teste.png`
- `grafico_cdf_meu_teste.png`

### Para comparar cenários

```bash
python3 comparar_cenarios.py \
    --cenario "Isolado:resultados/latencias_isolado.csv" \
    --cenario "Sem controle:resultados/latencias_sem_controle.csv" \
    --cenario "Preventivo:resultados/latencias_preventivo.csv" \
    --cenario "Reativo:resultados/latencias_reativo.csv" \
    --saida resultados/comparacao
```

Gera `resultados/comparacao_tabela.txt`, `resultados/comparacao_boxplot.png`
e `resultados/comparacao_barras.png`. O `executar_bateria_testes.sh` já faz
isso automaticamente.

## Conceitos estatísticos usados (para citar na seção de Avaliação do artigo)

| Conceito | Onde aparece | O que revela |
|---|---|---|
| **Média e mediana** | resumo `.txt`, histograma | Tendência central da latência. Quando média > mediana, indica cauda longa à direita (picos ocasionais de latência), comum em filas de rede. |
| **Desvio padrão** | resumo `.txt` | Dispersão/variabilidade da latência — quanto menor, mais previsível o comportamento do uRLLC. |
| **Percentis (p50, p75, p90, p95, p99)** | resumo `.txt`, gráfico CDF | Métrica padrão em SLAs de redes 5G/uRLLC: "95% das amostras ficaram abaixo de X ms". Mais robusta que a média a valores extremos. |
| **Intervalo de confiança de 95% (distribuição t de Student)** | resumo `.txt`, gráfico de barras da comparação | Faixa em que a verdadeira latência média da população provavelmente está, dado o tamanho finito da amostra coletada. |
| **Histograma** | `grafico_histograma_*.png` | Formato da distribuição de latências (unimodal, cauda longa, etc.). |
| **Função de distribuição cumulativa empírica (ECDF/CDF)** | `grafico_cdf_*.png` | Para qualquer limiar de latência, mostra diretamente a fração de amostras abaixo dele — a forma mais direta de checar o cumprimento do requisito de 5 ms. |
| **Boxplot (mediana, quartis, outliers)** | `grafico_boxplot_*.png`, `comparacao_boxplot.png` | Compara visualmente a dispersão e os valores extremos entre múltiplos cenários lado a lado. |
| **Série temporal com eventos de controle** | `grafico_serie_temporal_*.png` | Evidencia o efeito prático do closed loop: latência caindo logo após o controle ser ativado (linhas verdes) e voltando ao normal quando desativado (linhas laranjas). |
| **Taxa de violação do limiar (% de amostras > 5 ms)** | resumo `.txt`, tabela de comparação | Métrica direta de cumprimento (ou não) do requisito uRLLC do projeto. |

## Como funciona o controle Closed Loop

1. O **monitor** (`monitor_controlador.py`), rodando na Central de
   Monitoramento (`c_urllc`), escuta na porta TCP 5000 e atende, em
   threads concorrentes, os alertas dos 3 sensores dos prédios do campus
   simultaneamente, calculando a latência one-way de cada alerta.
2. Se duas medições consecutivas (de qualquer prédio) ultrapassam 5 ms, o
   monitor escreve um sinal `ativar` em um arquivo compartilhado.
3. O **orquestrador** (`experimento.py`), que tem acesso aos switches OVS,
   lê esse sinal e instala uma regra OpenFlow que descarta o tráfego eMBB
   (as portas UDP 5001-5003, uma por câmera) nos 4 switches — liberando
   banda/prioridade para os alertas de incêndio dos 3 prédios de uma vez.
4. Quando a latência normaliza (3 medições consecutivas abaixo de 5 ms), o
   monitor envia `desativar` e o vídeo das câmeras volta a fluir
   normalmente.
5. No modo `--controle preventivo`, esse drop já é aplicado desde o início
   do experimento, sem esperar a primeira violação.

As estatísticas finais (`analisar_resultados.py`) agregam as medições dos
3 prédios em um único CSV de latências, já que todos compartilham o mesmo
requisito de 5 ms perante a central.

## Solução de problemas

- **`docker compose build` falha ao instalar `mininet`**: verifique sua
  conexão de rede; o build baixa pacotes do repositório `universe` do
  Ubuntu. Rode `docker compose build --no-cache` para tentar de novo do
  zero.
- **Erro de permissão ao criar namespaces/interfaces dentro do container**:
  confirme que `privileged: true` está presente no `docker-compose.yml`
  (já vem configurado) e que o Docker Desktop está com "Virtualization
  Framework"/recursos padrão habilitados.
- **`docker compose run` fica preso limpando ambiente**: rode
  `docker compose down` e tente novamente; `topologia.py` já limpa
  automaticamente bridges OVS e interfaces residuais de execuções
  anteriores (`limpar_ambiente()`).
- **Nenhuma latência coletada (`resumo_estatistico_*.txt` vazio)**: veja os
  logs em `/tmp/log_monitor.txt`, `/tmp/log_gerador_urllc.txt` e
  `/tmp/log_cliente_iperf.txt` dentro do container para diagnosticar se o
  gerador conseguiu conectar no monitor.
