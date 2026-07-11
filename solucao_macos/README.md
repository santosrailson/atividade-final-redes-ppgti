# Closed loop uRLLC/eMBB em Mininet

Protótipo para avaliar um sistema de monitoramento e controle de aplicações
sensíveis à latência em uma rede de transporte 5G emulada. A solução preserva
tráfego uRLLC TCP gerado com Scapy, tráfego eMBB com `iperf3`, quatro nós OVS e
atuação em tempo real quando a latência one-way excede 5 ms.

## Pré-requisitos

- macOS com Docker Desktop e Docker Compose v2;
- ao menos 4 CPUs e 6 GB de memória disponíveis para o Docker;
- nenhuma instalação local de Mininet é necessária.

## Construção e teste rápido

```bash
docker compose build
docker compose run --rm urllc-lab python3 -m unittest discover -s tests -v
docker compose run --rm urllc-lab python3 experimento.py --duracao 30 --controle reativo
```

O container precisa de `privileged: true` exclusivamente para criar namespaces,
interfaces virtuais e regras OVS/tc. Não execute código não confiável nele.

## Experimento recomendado

```bash
docker compose run --rm \
  -e REPETICOES=5 -e DURACAO=60 -e TAXA_EMBB=12M \
  urllc-lab ./executar_bateria_testes.sh
```

A topologia usa backbone de 20 Mbit/s. Três fluxos eMBB de 12 Mbit/s criam
contenção de forma intencional. Os quatro grupos avaliados são:

1. `isolado`: uRLLC sem eMBB;
2. `sem_qos`: uRLLC + eMBB, sem classificação estática nem closed loop;
3. `qos_estatico`: fila prioritária fixa, sem realimentação;
4. `reativo`: fila prioritária e closed loop que reduz a taxa do eMBB, sem
   interrompê-lo completamente.

Use no mínimo cinco repetições. Não rode aplicações pesadas em paralelo e
registre versão do Docker, hardware, duração, taxa e seed/horário no artigo.

## Saídas

Cada execução cria uma pasta em `resultados/execucoes/<cenario>/rep_XX/` com:

- `latencias_urllc.csv`: timestamp, site, sequência e latência one-way;
- `eventos_controle.txt`: ativações/desativações e tempos;
- logs do monitor, sensores e fluxos eMBB;
- `resumo_estatistico_*.txt` e gráficos.

A bateria consolida as repetições em `resultados/comparacao_*`, mantendo os
dados brutos necessários para auditoria e reprodução.

## Parâmetros principais

```text
--duracao SEGUNDOS
--taxa-embb 12M
--tipo-embb udp|tcp
--controle nenhum|reativo
--qos-estatico / --sem-qos-estatico
--sem-embb
--diretorio-saida CAMINHO
```

O limiar é 5 ms. A ativação requer duas violações consecutivas e a liberação,
três amostras normais. O controlador reduz a fila eMBB para 2 Mbit/s por porta
durante a proteção e restaura 20 Mbit/s após a normalização.

## Guia acadêmico

Abra `guia_relatorio.html` no navegador. Ele explica como escrever Introdução,
Metodologia, Proposta, Avaliação e Conclusões, incluindo estratégias, tabelas,
figuras e ameaças à validade. Ele é um roteiro de escrita, não um artigo pronto.

## Limitações

- Os quatro nós de transporte são switches OpenFlow L2, uma abstração de
  roteadores programáveis; isso deve ser declarado no relatório.
- Os namespaces compartilham o relógio da mesma VM, tornando válida a medição
  one-way neste laboratório. Em equipamentos reais seria necessário PTP/NTP.
- Docker Desktop acrescenta jitter. Por isso, resultados devem usar repetições,
  percentis e taxa de violação, e não apenas uma média isolada.
