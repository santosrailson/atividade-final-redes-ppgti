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

---

## 📁 Estrutura do Repositório

```
.
├── README.md                          # Este arquivo
├── doc_project.md                     # Documentação detalhada do projeto
├── mininet/                           # Topologia e configuração da rede
│   └── topologia.py                   # Topologia Mininet com 4 switches P4 e 4 hosts
├── p4/                                # Código e regras dos switches P4
│   ├── comutador.p4                   # Plano de dados P4
│   └── tabelas/                       # Regras de encaminhamento/classificação
│       ├── c1.txt
│       ├── c2.txt
│       ├── c3.txt
│       └── c4.txt
├── traffic/                           # Geração de tráfego
│   ├── urllc/                         # Scripts Scapy para uRLLC (em desenvolvimento)
│   └── embb/                          # Scripts iperf/ffmpeg para eMBB (em desenvolvimento)
├── control/                           # Scripts de controle e monitoramento (em desenvolvimento)
├── util/                              # Scripts auxiliares
│   └── executar_topologia.sh          # Inicializa a topologia Mininet
├── results/                           # Logs e resultados dos experimentos
└── docs/                              # Relatório e documentação
```

---

## 🚀 Como executar

### Requisitos

- Mininet
- `p4c` (compilador P4)
- `simple_switch` e `simple_switch_CLI`
- Python 3, Scapy e o módulo `p4_mininet`

> No ambiente Debian 13 utilizado, o Mininet foi instalado via `apt`, e o `p4c`/`behavioral-model` foram compilados do código-fonte. Os scripts auxiliares de instalação estão em `util/instalar_p4*.sh`.

### Subir a topologia

```bash
sudo ./util/executar_topologia.sh
```

Ou diretamente com Python:

```bash
sudo python3 mininet/topologia.py --cli
```

Para mais detalhes sobre a topologia, o código P4 e as regras de encaminhamento, consulte o arquivo `doc_project.md`.

---

## 📅 Cronograma

| Etapa | Status | Descrição |
|-------|--------|-----------|
| Planejamento | ✅ Concluído | Definição da topologia e arquitetura do sistema |
| Implementação | 🔄 Em andamento | Desenvolvimento dos scripts e configurações |
| Testes e Validação | ⏳ Pendente | Execução de experimentos e coleta de resultados |
| Relatório | ⏳ Pendente | Escrita do artigo final |
| Entrega | ⏳ Pendente | Publicação no GitHub e envio do relatório |

---

## 👤 Autor

- **Railson Santos** — PPGTI, Instituto Federal da Paraíba (IFPB)

---

> **Nota:** Este projeto está em desenvolvimento. O `README.md` e o `doc_project.md` serão atualizados conforme novas seções forem concluídas.
