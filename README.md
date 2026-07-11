# Monitoramento Closed Loop para Aplicações uRLLC em Rede 5G

Projeto final da disciplina **Redes de Computadores — PPGTI/UFPB**. O
repositório implementa e avalia um sistema de monitoramento e controle em
malha fechada para proteger aplicações uRLLC com requisito de latência
one-way de até **5 ms**, mesmo quando coexistem com tráfego eMBB de alto
volume.

> O protótipo busca reduzir violações do limiar no ambiente emulado. Os
> resultados devem ser interpretados estatisticamente; não representam uma
> garantia universal de latência em uma rede 5G real.

## Cenário

O laboratório representa um campus com três locais — Biblioteca,
Laboratórios e Reitoria — conectados a uma Central de Monitoramento:

- sensores de incêndio geram tráfego **uRLLC TCP** com Scapy;
- câmeras geram tráfego **eMBB UDP/TCP** com iperf3;
- quatro switches Open vSwitch representam os nós programáveis da rede de
  transporte;
- o monitor mede cada mensagem, decide com histerese e atua nas filas OVS.

```text
sens_bib + cam_bib ── r1 ── r2 ── r3 ── r4 ── c_urllc + c_video
                         │      │
                  sens_lab   sens_rei
                  cam_lab    cam_rei
```

Os três enlaces do backbone têm 20 Mbit/s e 1 ms de atraso emulado. Três
fluxos eMBB de 12 Mbit/s criam contenção intencional para permitir uma
comparação mensurável entre as políticas.

## Estratégia de controle

O tráfego TCP na porta 5000 é classificado como uRLLC e encaminhado pela fila
de alta prioridade. Quando duas medições consecutivas excedem 5 ms, o closed
loop reduz a taxa máxima das filas eMBB de 20 para 2 Mbit/s. Após três
medições normais consecutivas, a taxa é restaurada.

O eMBB permanece ativo durante a proteção; a solução atual não descarta todo
o tráfego de vídeo.

## Cenários avaliados

1. **Isolado:** uRLLC sem tráfego eMBB.
2. **Sem QoS:** uRLLC e eMBB sem classificação prioritária nem atuação.
3. **QoS estático:** classificação em filas, sem realimentação.
4. **Closed loop:** QoS estático mais limitação reativa do eMBB.

Essa separação permite medir o efeito da contenção, o ganho da priorização
estática e o ganho incremental da realimentação.

## Execução rápida no macOS

O Mininet depende de recursos do kernel Linux. No macOS, toda a solução roda
em um container privilegiado dentro da VM do Docker Desktop.

Pré-requisitos:

- Docker Desktop com Docker Compose v2;
- pelo menos 4 CPUs e 6 GB de memória disponíveis para o Docker.

```bash
cd solucao_macos
docker compose build
docker compose run --rm urllc-lab python3 -m unittest discover -s tests -v
docker compose run --rm urllc-lab python3 experimento.py \
  --duracao 60 --taxa-embb 12M --controle reativo
```

## Bateria experimental

Para uma avaliação acadêmica, use várias execuções independentes por
cenário. O comando recomendado executa cinco repetições de 60 segundos:

```bash
cd solucao_macos
docker compose run --rm \
  -e REPETICOES=5 -e DURACAO=60 -e TAXA_EMBB=12M \
  urllc-lab ./executar_bateria_testes.sh
```

Para uma verificação mais curta com uma repetição por cenário:

```bash
docker compose run --rm \
  -e REPETICOES=1 -e DURACAO=60 -e TAXA_EMBB=12M \
  urllc-lab ./executar_bateria_testes.sh
```

## Resultados

A bateria preserva os dados em `solucao_macos/resultados/`:

```text
resultados/
├── manifesto_experimento.txt
├── comparacao_tabela.txt
├── comparacao_barras.png
├── comparacao_boxplot.png
├── latencias_<cenario>.csv
└── execucoes/
    └── <cenario>/rep_XX/
        ├── latencias_urllc.csv
        ├── eventos_controle.txt
        ├── resumo_estatistico_*.txt
        ├── logs
        └── gráficos
```

Cada amostra registra timestamp de recebimento, IP, site, sequência e
latência. A comparação apresenta média, mediana, desvio padrão, p95, p99 e
percentual acima de 5 ms. O intervalo de confiança comparativo é calculado
entre médias de repetições independentes, evitando tratar pacotes
correlacionados como experimentos independentes.

## Estrutura principal

```text
.
├── README.md
└── solucao_macos/
    ├── README.md                    # documentação operacional detalhada
    ├── guia_relatorio.html          # roteiro das cinco seções acadêmicas
    ├── Dockerfile
    ├── docker-compose.yml
    ├── topologia.py
    ├── experimento.py
    ├── protocolo_urllc.py
    ├── gerador_urllc.py
    ├── gerador_embb.py
    ├── monitor_controlador.py
    ├── analisar_resultados.py
    ├── comparar_cenarios.py
    ├── executar_bateria_testes.sh
    ├── tests/
    └── resultados/
```

## Documentação

- Consulte [`solucao_macos/README.md`](solucao_macos/README.md) para todos os
  parâmetros, comandos, saídas e limitações.
- Abra [`solucao_macos/guia_relatorio.html`](solucao_macos/guia_relatorio.html)
  para orientações sobre Introdução, Metodologia, Proposta, Avaliação e
  Conclusões.
- O enunciado original está em
  [`solucao_macos/PPGTI___RC___Projeto_Final.pdf`](solucao_macos/PPGTI___RC___Projeto_Final.pdf).

## Limitações

- Os quatro nós OVS são uma abstração L2 do plano de encaminhamento de uma
  rede de transporte programável, não roteadores IP completos.
- Os namespaces compartilham o relógio da VM, o que viabiliza one-way delay no
  laboratório; uma implantação física exigiria sincronização PTP/NTP.
- Docker Desktop e o datapath userspace introduzem jitter adicional.
- Uma única execução serve apenas como teste funcional. Conclusões
  estatísticas devem usar múltiplas repetições.
