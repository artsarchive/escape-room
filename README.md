# 🚪 Escape Room — Jogo Cooperativo Cliente-Servidor

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-desenvolvimento-yellow.svg)]()

Sistema de jogo cooperativo multiplayer implementado em arquitetura cliente-servidor, executado via interface de linha de comando (CLI). Desenvolvido como projeto prático da disciplina de Redes de Computadores.

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Motivação pela Escolha do TCP](#-motivação-pela-escolha-do-tcp)
- [Requisitos Mínimos](#-requisitos-mínimos)
- [Como Executar](#-como-executar)
- [Protocolo de Aplicação — ERP/1.0](#-protocolo-de-aplicação--erp10)
  - [Formato das Mensagens](#-formato-das-mensagens)
  - [Estados do Servidor](#-estados-do-servidor)
  - [Mensagens Cliente → Servidor](#-mensagens-cliente--servidor)
  - [Mensagens Servidor → Cliente](#-mensagens-servidor--cliente)
  - [Códigos de Erro](#-códigos-de-erro)
  - [Fluxo Completo da Sessão](#-fluxo-completo-da-sessão)
  - [Regras de Unicast e Broadcast](#-regras-de-unicast-e-broadcast)
  - [Tratamento de Desconexão](#-tratamento-de-desconexão)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Comandos do Jogo](#-comandos-do-jogo)
- [Salas e Enigmas](#-salas-e-enigmas)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## 🎯 Sobre o Projeto

O sistema é um jogo de **Escape Room cooperativo** onde **2 a 4 jogadores** conectados simultaneamente em rede local colaboram para resolver enigmas, compartilhar pistas e executar ações coordenadas com o objetivo de escapar de uma sala virtual dentro de um limite de tempo.

A aplicação é executada inteiramente via terminal, sem dependências externas além da biblioteca padrão do Python. A comunicação entre os jogadores é mediada exclusivamente pelo servidor, que centraliza todo o estado do jogo e propaga eventos em tempo real para todos os clientes conectados.

### 🎓 Objetivos Educacionais

- Implementação de sockets TCP em Python
- Desenvolvimento de protocolo de camada de aplicação
- Gerenciamento de estados em sistemas distribuídos
- Comunicação concorrente com múltiplos clientes via threads

---

## 🔌 Motivação pela Escolha do TCP

O protocolo de transporte utilizado é o **TCP (Transmission Control Protocol)**. A escolha se justifica por:

| Característica | Benefício para o Jogo |
|----------------|----------------------|
| **Entrega garantida** | Cada ação altera o estado persistente. Uma mensagem perdida tornaria o estado inconsistente. |
| **Ordem garantida** | Ações dependem umas das outras sequencialmente. Executar B antes de A pode invalidar a jogada. |
| **Sem perdas aceitáveis** | Diferente de mídia em tempo real, cada mensagem carrega uma mutação irreversível de estado. |
| **Conexões de longa duração** | Gerencia naturalmente sessões persistentes durante toda a partida. |
| **Simplicidade** | Uso de `readline()` com delimitador `\n` simplifica a separação de mensagens. |

---

## 📦 Requisitos Mínimos

### Servidor

- Python 3.8 ou superior
- Módulos: `socket`, `threading`, `json`, `uuid`, `time` (todos da biblioteca padrão)
- Porta TCP 5000 disponível (configurável via `--port`)

### Cliente

- Python 3.8 ou superior
- Acesso à rede local (LAN) ou localhost
- Terminal com suporte a UTF-8
- Nenhuma biblioteca externa necessária

### Limites da Sessão

| Parâmetro | Valor |
|-----------|-------|
| Mínimo de jogadores | 2 |
| Máximo de jogadores | 4 |
| Tempo limite da partida | 30 minutos |
| Contagem regressiva antes do início | 10 segundos |
| Intervalo de atualização do timer | 30 segundos |

---

## 🚀 Como Executar

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/escape-room.git
cd escape-room
