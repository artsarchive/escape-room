# Escape Room — Jogo Cooperativo Cliente-Servidor

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-desenvolvimento-yellow.svg)]()

Sistema de jogo cooperativo multiplayer implementado em arquitetura cliente-servidor, executado via interface de linha de comando (CLI). Desenvolvido como projeto prático da disciplina de Redes de Computadores.

---

## Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Motivação pela Escolha do TCP](#-motivação-pela-escolha-do-tcp)
- [Requisitos Mínimos](#-requisitos-mínimos)
- [Como Executar](#-como-executar)
- [Protocolo de Aplicação — ERP/1.0](#-protocolo-de-aplicação--erp10)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Comandos do Jogo](#-comandos-do-jogo)
- [Salas e Enigmas](#-salas-e-enigmas)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## Sobre o Projeto

O sistema é um jogo de **Escape Room cooperativo** onde **2 a 4 jogadores** conectados simultaneamente em rede local colaboram para resolver enigmas, compartilhar pistas e executar ações coordenadas com o objetivo de escapar de uma sala virtual dentro de um limite de tempo.

A aplicação é executada inteiramente via terminal, sem dependências externas além da biblioteca padrão do Python. A comunicação entre os jogadores é mediada exclusivamente pelo servidor, que centraliza todo o estado do jogo e propaga eventos em tempo real para todos os clientes conectados.

### Objetivos Educacionais

- Implementação de sockets TCP em Python
- Desenvolvimento de protocolo de camada de aplicação
- Gerenciamento de estados em sistemas distribuídos
- Comunicação concorrente com múltiplos clientes via threads

---

## Motivação pela Escolha do TCP

O protocolo de transporte utilizado é o **TCP (Transmission Control Protocol)**. A escolha se justifica por:

| Característica | Benefício para o Jogo |
|----------------|----------------------|
| **Entrega garantida** | Cada ação altera o estado persistente. Uma mensagem perdida tornaria o estado inconsistente. |
| **Ordem garantida** | Ações dependem umas das outras sequencialmente. Executar B antes de A pode invalidar a jogada. |
| **Sem perdas aceitáveis** | Diferente de mídia em tempo real, cada mensagem carrega uma mutação irreversível de estado. |
| **Conexões de longa duração** | Gerencia naturalmente sessões persistentes durante toda a partida. |
| **Simplicidade** | Uso de `readline()` com delimitador `\n` simplifica a separação de mensagens. |

---

## Requisitos Mínimos

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

## Como Executar

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/escape-room.git
cd escape-room
```

### 2. Inicie o servidor

```bash
python server.py
```

**Com parâmetros personalizados:**

```bash
python server.py --host 0.0.0.0 --port 5000
```

### 3. Conecte os clientes

Em terminais separados para cada jogador:

```bash
python client.py
```

**Conectando a um servidor remoto:**

```bash
python client.py --host 192.168.1.10 --port 5000
```

> **Nota:** Cada cliente solicitará um nome de usuário ao iniciar. Após todos os jogadores conectados digitarem `READY`, uma contagem regressiva de 10 segundos é iniciada e o jogo começa.

---

## Protocolo de Aplicação — ERP/1.0

O **ERP (Escape Room Protocol)** versão 1.0 define o formato de todas as mensagens trocadas entre clientes e servidor.

### Formato das Mensagens

Todas as mensagens são objetos **JSON serializados**, seguidos do caractere delimitador `\n` (newline).

```json
{"type": "TIPO_DA_MENSAGEM", "payload": { ... }}\n
```

- `type`: identifica o tipo da mensagem
- `payload`: dados específicos de cada tipo (ambos obrigatórios)

### Estados do Servidor

```
WAITING_PLAYERS → COUNTDOWN → IN_GAME → GAME_OVER
        ↑                                    │
        └────────────── reset (10s) ─────────┘
```

| Estado | Descrição |
|--------|-----------|
| **WAITING_PLAYERS** | Lobby aberto. Aceita JOIN e READY. Aguarda mínimo de 2 jogadores prontos. |
| **COUNTDOWN** | Início iminente. Envia contagem regressiva por 10 segundos. Não aceita novos JOINs. |
| **IN_GAME** | Partida ativa. Aceita ACTION e CHAT. Timer em execução. |
| **GAME_OVER** | Partida encerrada. Após 10 segundos, reseta para WAITING_PLAYERS. |

### Mensagens: Cliente → Servidor

| Tipo | Payload | Quando usar |
|------|---------|-------------|
| `JOIN` | `{"username": "nome"}` | Primeira mensagem ao conectar. |
| `READY` | `{}` | Sinaliza que está pronto no lobby. |
| `ACTION` | `{"command": "examinar mesa"}` | Ação no jogo. Válido apenas em IN_GAME. |
| `CHAT` | `{"message": "texto livre"}` | Mensagem para todos. Válido em IN_GAME. |
| `DISCONNECT` | `{}` | Saída voluntária. |

**Exemplos:**

```json
{"type": "JOIN", "payload": {"username": "Lucas"}}\n
{"type": "ACTION", "payload": {"command": "examinar cofre"}}\n
{"type": "CHAT", "payload": {"message": "Achei a chave!"}}\n
```

### Mensagens: Servidor → Cliente

| Tipo | Payload principal | Tipo de Envio |
|------|-------------------|---------------|
| `WELCOME` | `{player_id, server_state}` | **Unicast** |
| `LOBBY_UPDATE` | `{players[], ready_count, total}` | **Broadcast** |
| `COUNTDOWN` | `{seconds: N}` | **Broadcast** |
| `GAME_START` | `{room, description, time_limit}` | **Broadcast** |
| `ACTION_RESULT` | `{success, message, state_changed}` | **Unicast** |
| `ROOM_UPDATE` | `{room_state{}, objects[], players_here[]}` | **Broadcast** |
| `CHAT_BROADCAST` | `{from, message}` | **Broadcast** |
| `TIMER_UPDATE` | `{remaining: N}` | **Broadcast** |
| `PLAYER_EVENT` | `{event, player, detail}` | **Broadcast** |
| `HINT` | `{text}` | **Unicast** |
| `GAME_OVER` | `{result, time_elapsed, message}` | **Broadcast** |
| `ERROR` | `{code, message}` | **Unicast** |

**Exemplos:**

```json
{"type": "WELCOME", "payload": {"player_id": "a3f1b2c4", "server_state": "WAITING_PLAYERS"}}\n
{"type": "ACTION_RESULT", "payload": {"success": true, "message": "Você encontrou uma chave vermelha!", "state_changed": true}}\n
{"type": "GAME_OVER", "payload": {"result": "win", "time_elapsed": 923, "message": "Vocês escaparam em 15m 23s!"}}\n
```

### Códigos de Erro

| Código | Situação |
|--------|----------|
| `NAME_TAKEN` | O username já está em uso na sessão atual. |
| `GAME_FULL` | Já existem 4 jogadores conectados (limite máximo). |
| `GAME_IN_PROGRESS` | Tentativa de JOIN enquanto o estado é IN_GAME. |
| `INVALID_ACTION` | Comando malformado ou ação fora de contexto. |
| `NOT_IN_GAME` | Mensagem enviada fora do estado IN_GAME. |

**Exemplo:**

```json
{"type": "ERROR", "payload": {"code": "NAME_TAKEN", "message": "O nome 'Lucas' já está em uso. Escolha outro username."}}\n
```

### Fluxo Completo da Sessão

```
CLIENTE A                  SERVIDOR                 CLIENTE B
    │                          │                         │
    │──── JOIN ───────────────►│                         │
    │◄─── WELCOME ────────────│                         │
    │◄─── LOBBY_UPDATE ───────│                         │
    │                          │◄────────── JOIN ────────│
    │◄─── LOBBY_UPDATE ───────│──── WELCOME ───────────►│
    │                          │──── LOBBY_UPDATE ──────►│
    │                          │                         │
    │──── READY ──────────────►│                         │
    │                          │◄────────── READY ───────│
    │◄─── LOBBY_UPDATE ───────│──── LOBBY_UPDATE ──────►│
    │                          │                         │
    │◄─── COUNTDOWN(10) ──────│──── COUNTDOWN(10) ─────►│
    │◄─── COUNTDOWN(9)  ──────│──── COUNTDOWN(9)  ─────►│
    │          ...             │          ...             │
    │◄─── GAME_START ─────────│──── GAME_START ─────────►│
    │                          │                         │
    │──── ACTION("examinar mesa") ───────────────────────►│
    │◄─── ACTION_RESULT ──────│                         │
    │◄─── ROOM_UPDATE ────────│──── ROOM_UPDATE ────────►│
    │                          │                         │
    │──── CHAT("Achei algo!") ─────────────────────────►│
    │◄─── CHAT_BROADCAST ─────│──── CHAT_BROADCAST ─────►│
    │                          │                         │
    │◄─── TIMER_UPDATE(1745) ─│──── TIMER_UPDATE(1745) ►│
    │                          │                         │
    │◄══════════════════════ GAME_OVER ══════════════════►│
```

### Regras de Unicast e Broadcast

| Tipo de envio | Mensagens |
|---------------|-----------|
| **Unicast** (somente ao remetente) | `WELCOME`, `ACTION_RESULT`, `HINT`, `ERROR` |
| **Broadcast** (todos os clientes) | `LOBBY_UPDATE`, `COUNTDOWN`, `GAME_START`, `ROOM_UPDATE`, `CHAT_BROADCAST`, `TIMER_UPDATE`, `PLAYER_EVENT`, `GAME_OVER` |

### Tratamento de Desconexão

- **Durante WAITING_PLAYERS**: Remove o jogador, envia `PLAYER_EVENT` com `event: "left"` e `LOBBY_UPDATE` atualizado.
- **Durante IN_GAME**: Envia `PLAYER_EVENT` com `event: "left"`. Se restar menos de 1 jogador, encerra com `GAME_OVER` e `result: "lose"`.
- **Desconexão abrupta**: Detectada via exceção no `recv()` — tratada de forma idêntica à desconexão voluntária.

---

## Estrutura do Projeto

```
escape-room/
├── server.py              # Servidor TCP principal
├── client.py              # Cliente CLI
├── game/
│   ├── __init__.py
│   ├── protocol.py        # Constantes e serialização do ERP/1.0
│   ├── rooms.py           # Definição das salas, objetos e enigmas
│   └── state.py           # Gerenciamento de estado da partida
└── README.md
```

### Módulos

| Arquivo | Responsabilidade |
|---------|------------------|
| `game/protocol.py` | Constantes do protocolo, funções encode/decode, builders de mensagens |
| `game/rooms.py` | 3 salas com objetos, descrições, enigmas encadeados e dicas progressivas |
| `game/state.py` | Processa comandos, aplica efeitos no estado e detecta condição de vitória |
| `server.py` | Aceita conexões, cria threads, protege estado compartilhado, gerencia ciclo da partida |
| `client.py` | Conecta ao servidor, thread dedicada para receber mensagens enquanto digita comandos |

---

## 🎮 Comandos do Jogo

| Comando | Exemplo | Descrição |
|---------|---------|-----------|
| `examinar <objeto>` | `examinar mesa` | Descreve o objeto em detalhe. Pode revelar objetos ocultos. |
| `pegar <objeto>` | `pegar chave_vermelha` | Adiciona o objeto ao inventário do jogador. |
| `usar <item> em <objeto>` | `usar chave_azul em porta_leste` | Combina um item do inventário com um objeto da sala. |
| `ir <direção>` | `ir leste` | Move para a sala adjacente (norte, sul, leste, oeste). |
| `inventario` | `inventario` | Lista os itens que o jogador carrega. |
| `dica` | `dica` | Solicita a próxima dica para a sala atual (progressiva). |
| `chat <mensagem>` | `chat Achei a chave!` | Envia mensagem para todos os jogadores. |
| `READY` | `READY` | No lobby: sinaliza que está pronto para iniciar. |
| `sair` | `sair` | Desconecta voluntariamente do servidor. |

---

## Salas e Enigmas

O jogo possui **3 salas encadeadas**. A progressão exige colaboração entre os jogadores.

### Sala 1 — Laboratório Abandonado 

Sala inicial. Contém:

- **Mesa** - com itens para examinar
- **Cofre de 4 dígitos** - requer código numérico
- **Quadro-negro** - com sequência numérica incompleta
- **Lixeira** - com uma anotação importante

**Objetivo**: Descobrir o código do cofre, obter a **chave azul** e destrancar a saída leste.

---

### Sala 2 — Corredor 

Acessível após resolver o laboratório. Contém:

- **Fotografias** - com instruções
- **Caixa de fusíveis** - com uma peça faltando
- **Tapete** - esconde a peça necessária

**Objetivo**: Encontrar o fusível correto, encaixá-lo e destrancar a porta norte.

---

### Sala 3 — Sala Final 

Acessível após o corredor. Contém:

- **Terminal de computador** - exige senha mestre
- **Placa na parede** - com código codificado
- **Diário aberto** - confirma a senha

**Objetivo**: Inserir a senha correta no terminal para abrir a saída principal e vencer.

