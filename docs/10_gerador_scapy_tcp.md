# Gerador uRLLC com Scapy/TCP

Para atender literalmente ao enunciado da atividade — que diz *"O tráfego URLLC deverá ser gerado e monitorado usando scripts em Python com Scapy, permitindo o envio e recepção de pacotes TCP"* — foram criadas versões do gerador e do monitor baseadas em **Scapy sobre TCP**.

## Arquivos criados

- `etapa3_solucao/gerador_urllc_scapy.py` — gerador TCP usando `StreamSocket` do Scapy.
- `etapa3_solucao/monitor_controlador_scapy.py` — receptor/controlador TCP usando `StreamSocket` do Scapy.
- `etapa3_solucao/gerador_urllc_scapy_otimizado.py` — versão com reutilização do pacote Scapy e `conf.verb = 0`.
- `etapa3_solucao/monitor_controlador_scapy_otimizado.py` — receptor otimizado correspondente.

## Como funciona

O `StreamSocket` do Scapy permite usar um socket TCP do sistema operacional como transporte, mas enviar/receber objetos Scapy. O pacote enviado é construído como:

```python
pacote = IP(dst=endereco_destino) / TCP(dport=porta_destino) / Raw(load=payload)
```

Onde `payload` contém o timestamp de envio em 8 bytes (`struct.pack("!d", timestamp_envio)`). O receptor extrai o timestamp, calcula a latência e devolve os mesmos 8 bytes.

## Integração nos orquestradores

O `experimento_4roteadores_urllc_curto.py` recebeu duas novas flags:

```bash
# Versao Scapy padrao
sudo ... experimento_4roteadores_urllc_curto.py ... --scapy

# Versao Scapy "otimizada"
sudo ... experimento_4roteadores_urllc_curto.py ... --scapy-otimizado
```

O `experimento_melhorias.py` também recebeu a flag `--scapy` para testes na topologia em linha.

## Resultados

### Caminho curto (2 saltos), 4 roteadores mantidos

| Versão do gerador | Cenário | Latência média (RTT) | % > 5 ms |
|---|---|---|---|
| Socket TCP puro | Sem eMBB | ~3,5 ms | ~15% |
| Socket TCP puro | +eMBB 3M UDP | ~3,8 ms | ~18% |
| **Scapy/TCP** | **Sem eMBB** | **~6,9 ms** | **~55%** |
| **Scapy/TCP** | **+eMBB 3M UDP** | **~7,6 ms** | **~61%** |
| Scapy/TCP "otimizado" | +eMBB 3M UDP | ~9,7 ms | ~62% |

## Análise

O uso do Scapy introduziu um **overhead significativo e consistente** de aproximadamente **3 ms a 4 ms** por medição em relação ao socket TCP puro. Esse overhead é suficiente para fazer a latência média ultrapassar o limiar de 5 ms, mesmo no melhor cenário de caminho curto e eMBB separado.

Possíveis causas do overhead:

- Construção e serialização do pacote Scapy (`IP/TCP/Raw`) a cada envio.
- Parse da resposta como objeto Scapy pelo `StreamSocket`.
- Gerenciamento interno de camadas e campos do Scapy.
- A versão "otimizada" não reduziu o overhead; em alguns casos foi ligeiramente pior, possivelmente por reutilização de objeto mutável no Scapy.

## Implicação para o projeto

Isso cria um dilema:

- **Requisito literal do enunciado**: usar Scapy em tráfego TCP.
- **Requisito de desempenho**: latência <= 5 ms.

No ambiente Mininet + BMv2 em software, **os dois requisitos não são simultaneamente atingíveis** com o caminho de 2 saltos testado. O Scapy adiciona overhead que impede a latência média de ficar consistentemente abaixo de 5 ms.

## Opções para o relatório

1. **Usar o gerador Scapy como implementação formal** e discutir no artigo que o overhead do Scapy no ambiente emulado impede o limiar de 5 ms, mas a arquitetura Closed Loop e o isolamento por roteamento são válidos.
2. **Manter o gerador socket TCP puro como principal** (pois atinge <= 5 ms) e disponibilizar o gerador Scapy como uma alternativa que atende literalmente ao requisito de uso do Scapy.
3. **Investigar uma implementação Scapy de mais baixo nível**, por exemplo usando `sendp`/`sniff` na camada 2 com TCP raw, mas essa abordagem é significativamente mais complexa e propensa a instabilidade no Mininet.

A opção 2 é a mais pragmática para demonstrar o cumprimento do objetivo principal (latência <= 5 ms), enquanto a opção 1 é mais fiel ao texto do enunciado.
