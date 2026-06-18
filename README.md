# Sistema de Monitoramento e Controle para Aplicações Sensíveis à Latência

> **Disciplina:** Redes de Computadores — PPGTI  
> **Professores:** Prof. Paulo Ditarso Maciel Jr. e Prof. Leandro Almeida  
> **Prazo de entrega:** 01/08/2026

---

## 📋 O que deve ser feito

Este projeto consiste no desenvolvimento de um **sistema de monitoramento e controle em *Closed Loop*** para aplicações do tipo **uRLLC** (*Ultra-Reliable Low Latency Communication*) em uma rede de transporte 5G.

### Contexto

Você atua como especialista de conectividade em uma operadora de telecomunicações que fornece conectividade 5G para diversos clientes. Sua missão é garantir que aplicações sensíveis à latência não excedam um **atraso fim-a-fim (End-to-End) de 5ms** na rede de transporte, coexistindo com outras classes de tráfego, como **eMBB** (*enhanced Mobile Broadband*), que demandam alto volume de dados.

### Objetivo

Desenvolver um mecanismo de *Closed Loop* que:

1. **Monitore continuamente** a latência dos fluxos uRLLC em tempo real;
2. **Meça a latência** de cada pacote TCP enviado e recebido (gerado com Scapy);
3. **Dispare ações corretivas** automaticamente quando a latência atingir o limiar de **5ms**;
4. **Atue na infraestrutura** ajustando filas e prioridades nos roteadores da rede de transporte;
5. **Diferencie o tráfego uRLLC do eMBB** usando filtros e classes de prioridade distintas;
6. **Crie um ciclo de feedback** onde o sistema mede o impacto das mudanças e reajusta, se necessário, mantendo a latência sempre abaixo de 5ms.

### Requisitos Técnicos

| Componente | Descrição |
|------------|-----------|
| **Emulação da rede** | Mininet com topologia contendo **quatro roteadores** da rede de transporte |
| **Tráfego uRLLC** | Scripts Python com **Scapy** (TCP) para envio, recepção e medição de latência em tempo real |
| **Tráfego eMBB** | Ferramentas como **iperf** ou **ffmpeg** para simular alta demanda de banda (ex: streaming de vídeo, transferência de arquivos) |
| **Controle** | Scripts que ajustam dinamicamente filas e prioridades nos roteadores em resposta à latência medida |

### Artefatos de Entrega

1. **Relatório final** em formato de artigo científico ([template SBC](https://pt.overleaf.com/latex/templates/sbc-conferences-template/blbxwjwzdngr)), contendo:
   - Introdução
   - Metodologia
   - Proposta
   - Avaliação
   - Conclusões

2. **Repositório no GitHub** com:
   - Scripts Python para envio e medição do tráfego uRLLC (Scapy)
   - Arquivos de configuração do Mininet
   - Scripts para geração de tráfego eMBB
   - Scripts de controle para ajuste de prioridade em tempo real
   - Instruções claras para execução e reprodução dos experimentos

---

## 📁 Estrutura do Repositório (em desenvolvimento)

```
.
├── README.md                          # Este arquivo
├── docs/                              # Relatório e documentação
├── mininet/                           # Topologia e configuração da rede
├── traffic/                           # Geração de tráfego
│   ├── urllc/                         # Scripts Scapy para uRLLC
│   └── embb/                          # Scripts iperf/ffmpeg para eMBB
├── control/                           # Scripts de controle e monitoramento
└── results/                           # Logs e resultados dos experimentos
```

---

## 🚀 Como executar (em breve)

> As instruções detalhadas de instalação, configuração e execução serão adicionadas conforme o projeto for implementado.

---

## 📅 Cronograma

| Etapa | Status | Descrição |
|-------|--------|-----------|
| Planejamento | 🔄 Em andamento | Definição da topologia e arquitetura do sistema |
| Implementação | ⏳ Pendente | Desenvolvimento dos scripts e configurações |
| Testes e Validação | ⏳ Pendente | Execução de experimentos e coleta de resultados |
| Relatório | ⏳ Pendente | Escrita do artigo final |
| Entrega | ⏳ Pendente | Publicação no GitHub e envio do relatório |

---

## 👤 Autor

- **Railson Santos** — PPGTI, Instituto Federal da Paraíba (IFPB)

---

> **Nota:** Este projeto está em desenvolvimento. O README será atualizado conforme novas seções e instruções forem concluídas.
