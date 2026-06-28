Escape Room — Jogo Cooperativo Cliente-Servidor
Sistema de jogo cooperativo multiplayer implementado em arquitetura cliente-servidor, executado via interface de linha de comando (CLI). Desenvolvido como projeto prático da disciplina de Redes de Computadores.
Sumário
Propósito da Aplicação
Motivação pela Escolha do TCP
Requisitos Mínimos de Funcionamento
Como Executar
Protocolo de Aplicação — ERP/1.0
5.1 Formato das Mensagens
5.2 Estados do Servidor
5.3 Mensagens: Cliente → Servidor
5.4 Mensagens: Servidor → Cliente
5.5 Códigos de Erro
5.6 Fluxo Completo de uma Sessão
5.7 Regras de Unicast e Broadcast
5.8 Tratamento de Desconexão
Estrutura do Projeto
Comandos do Jogo
Salas e Enigmas

1. Propósito da Aplicação
O sistema proposto é um jogo de Escape Room cooperativo, onde 2 a 4 jogadores conectados simultaneamente em rede local devem colaborar para resolver enigmas, compartilhar pistas e executar ações coordenadas com o objetivo de escapar de uma sala virtual dentro de um limite de tempo.
A aplicação é executada inteiramente via terminal, sem dependências externas além da biblioteca padrão do Python. A comunicação entre os jogadores é mediada exclusivamente pelo servidor, que centraliza todo o estado do jogo e propaga eventos em tempo real para todos os clientes conectados.
O projeto tem como finalidade aplicar conceitos de Redes de Computadores, com ênfase em:
Implementação de sockets TCP em Python
Desenvolvimento de protocolo de camada de aplicação
Gerenciamento de estados em sistemas distribuídos
Comunicação concorrente com múltiplos clientes via threads

2. Motivação pela Escolha do TCP
O protocolo de transporte utilizado é o TCP (Transmission Control Protocol). A escolha se justifica pelas seguintes razões:
Entrega garantida: cada ação de jogo (examinar, pegar, usar, ir) altera o estado persistente da partida. Uma mensagem perdida tornaria o estado do servidor inconsistente com o que o jogador vê no terminal, invalidando a experiência de jogo.
Ordem garantida: as ações dos jogadores dependem umas das outras de forma sequencial. Executar a ação B antes da ação A pode tornar a ação B impossível ou inválida (por exemplo, usar uma chave antes de pegá-la).
Sem perdas aceitáveis: diferente de aplicações de mídia em tempo real, onde descartar um frame de vídeo é tolerável, aqui cada mensagem carrega uma mutação de estado irreversível. Não há mecanismo de interpolação ou predição que compense perdas.
Conexões de longa duração: o TCP gerencia naturalmente sessões persistentes entre cliente e servidor durante toda a partida, eliminando a necessidade de reimplementar controle de conexão sobre UDP — sem qualquer benefício prático para o cenário de rede local.
Simplicidade de implementação: o uso de TCP com readline() (delimitador \n) simplifica a separação de mensagens no socket, evitando a necessidade de implementar fragmentação e remontagem manualmente.

3. Requisitos Mínimos de Funcionamento
Servidor
Python 3.8 ou superior
Módulos: socket, threading, json, uuid, time (todos da biblioteca padrão)
Porta TCP 5000 disponível (configurável via --port)
Mínimo de 2 jogadores conectados para iniciar a partida
Cliente
Python 3.8 ou superior
Acesso à rede local (LAN) ou localhost
Terminal com suporte a UTF-8
Nenhuma biblioteca externa necessária
Limites da sessão
Parâmetro
Valor
Mínimo de jogadores
2
Máximo de jogadores
4
Tempo limite da partida
30 minutos
Contagem regressiva antes do início
10 segundos
Intervalo de atualização do timer
30 segundos


4. Como Executar
1. Clone o repositório
git clone <url-do-repositório>
cd escape-room

2. Inicie o servidor
python server.py
# ou com parâmetros:
python server.py --host 0.0.0.0 --port 5000

3. Conecte os clientes (em terminais separados)
python client.py
# ou apontando para outro host:
python client.py --host 192.168.1.10 --port 5000

Cada cliente solicitará um nome de usuário ao iniciar. Após todos os jogadores conectados digitarem READY, uma contagem regressiva de 10 segundos é iniciada e o jogo começa.

5. Protocolo de Aplicação — ERP/1.0
O ERP (Escape Room Protocol) versão 1.0 é o protocolo de camada de aplicação desenvolvido para esta aplicação. Ele define o formato de todas as mensagens trocadas entre clientes e servidor, os estados do sistema e as transições permitidas entre eles.
5.1 Formato das Mensagens
Todas as mensagens são objetos JSON serializados, seguidos do caractere delimitador \n (newline). O delimitador permite o uso de readline() no socket para separação confiável de mensagens, mesmo quando múltiplas mensagens chegam no mesmo segmento TCP.
{"type": "TIPO_DA_MENSAGEM", "payload": { ... }}\n

O campo type identifica o tipo da mensagem. O campo payload carrega os dados específicos de cada tipo. Ambos são obrigatórios em toda mensagem.

5.2 Estados do Servidor
O servidor opera em quatro estados distintos. Apenas um estado é ativo por vez para toda a sessão de jogo.
WAITING_PLAYERS → COUNTDOWN → IN_GAME → GAME_OVER
        ↑                                    │
        └────────────── reset (10s) ─────────┘

Estado
Descrição
WAITING_PLAYERS
Lobby aberto. Aceita conexões e comandos JOIN e READY. Aguarda mínimo de 2 jogadores prontos.
COUNTDOWN
Condição de início atingida. Servidor envia COUNTDOWN a cada segundo por 10 segundos. Não aceita novos JOINs.
IN_GAME
Partida ativa. Aceita ACTION e CHAT. Timer em execução. Broadcast de eventos a todos os clientes.
GAME_OVER
Partida encerrada por vitória ou derrota. Envia GAME_OVER em broadcast. Após 10 segundos, reseta para WAITING_PLAYERS.


5.3 Mensagens: Cliente → Servidor
Tipo
Payload
Quando usar
JOIN
{"username": "nome"}
Primeira mensagem ao conectar. Deve ser enviada antes de qualquer outra.
READY
{}
Jogador sinaliza que está pronto no lobby. Válido apenas em WAITING_PLAYERS.
ACTION
{"command": "examinar mesa"}
Qualquer ação do jogador no jogo. Válido apenas em IN_GAME.
CHAT
{"message": "texto livre"}
Mensagem de chat para todos. Válido em IN_GAME.
DISCONNECT
{}
Saída voluntária. O servidor remove o jogador e notifica os demais.

Exemplos:
{"type": "JOIN", "payload": {"username": "Lucas"}}\n

{"type": "ACTION", "payload": {"command": "examinar cofre"}}\n

{"type": "CHAT", "payload": {"message": "Achei a chave!"}}\n


5.4 Mensagens: Servidor → Cliente
Tipo
Payload principal
Gatilho
WELCOME
{player_id, server_state}
Resposta ao JOIN bem-sucedido. Unicast.
LOBBY_UPDATE
{players[], ready_count, total}
Sempre que jogador entra, sai ou muda status. Broadcast.
COUNTDOWN
{seconds: N}
Repetido a cada segundo (10..1) antes de GAME_START. Broadcast.
GAME_START
{room, description, time_limit}
Início da partida. Broadcast.
ACTION_RESULT
{success, message, state_changed}
Resposta individual ao ACTION do jogador. Unicast.
ROOM_UPDATE
{room_state{}, objects[], players_here[]}
Broadcast quando o estado da sala muda após uma ação.
CHAT_BROADCAST
{from, message}
Reencaminha CHAT para todos. Broadcast.
TIMER_UPDATE
{remaining: N}
A cada 30s e nos marcos críticos (60s, 30s, 10s). Broadcast.
PLAYER_EVENT
{event: joined|left|moved, player, detail}
Notifica eventos de outros jogadores. Broadcast.
HINT
{text}
Dica solicitada via comando dica ou emitida automaticamente. Unicast.
GAME_OVER
{result: win|lose, time_elapsed, message}
Fim de jogo. Broadcast.
ERROR
{code, message}
Erro de protocolo ou de lógica de jogo. Unicast.

Exemplos:
{"type": "WELCOME", "payload": {"player_id": "a3f1b2c4", "server_state": "WAITING_PLAYERS"}}\n

{"type": "ACTION_RESULT", "payload": {"success": true, "message": "Você encontrou uma chave vermelha!", "state_changed": true}}\n

{"type": "GAME_OVER", "payload": {"result": "win", "time_elapsed": 923, "message": "Vocês escaparam em 15m 23s!"}}\n


5.5 Códigos de Erro
Erros são enviados como mensagem ERROR com um campo code padronizado e um campo message legível para exibição ao usuário.
Código
Situação
NAME_TAKEN
O username escolhido já está em uso na sessão atual.
GAME_FULL
Já existem 4 jogadores conectados (limite máximo).
GAME_IN_PROGRESS
Tentativa de JOIN enquanto o estado é IN_GAME.
INVALID_ACTION
Comando malformado, objeto inexistente ou ação fora de contexto.
NOT_IN_GAME
Mensagem ACTION ou CHAT enviada fora do estado IN_GAME.

Exemplo:
{"type": "ERROR", "payload": {"code": "NAME_TAKEN", "message": "O nome 'Lucas' já está em uso. Escolha outro username."}}\n


5.6 Fluxo Completo de uma Sessão
Diagrama de sequência com 2 jogadores:
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
    │──── ACTION("examinar mesa") ───────────────────────►... (servidor processa)
    │◄─── ACTION_RESULT ──────│                         │
    │◄─── ROOM_UPDATE ────────│──── ROOM_UPDATE ────────►│
    │                          │                         │
    │──── CHAT("Achei algo!") ─────────────────────────► (servidor processa)
    │◄─── CHAT_BROADCAST ─────│──── CHAT_BROADCAST ─────►│
    │                          │                         │
    │◄─── TIMER_UPDATE(1745) ─│──── TIMER_UPDATE(1745) ►│
    │                          │                         │
    │◄══════════════════════ GAME_OVER ══════════════════►│


5.7 Regras de Unicast e Broadcast
Tipo de envio
Mensagens
Unicast (somente ao remetente)
WELCOME, ACTION_RESULT, HINT, ERROR
Broadcast (todos os clientes)
LOBBY_UPDATE, COUNTDOWN, GAME_START, ROOM_UPDATE, CHAT_BROADCAST, TIMER_UPDATE, PLAYER_EVENT, GAME_OVER


5.8 Tratamento de Desconexão
Durante WAITING_PLAYERS: o servidor remove o jogador, envia PLAYER_EVENT com event: "left" e um LOBBY_UPDATE atualizado para os demais.
Durante IN_GAME: o servidor envia PLAYER_EVENT com event: "left". O jogo continua com os jogadores restantes. Se restar menos de 1 jogador, o servidor encerra a partida com GAME_OVER e result: "lose".
Desconexão abrupta (sem envio de DISCONNECT): detectada via exceção no recv() — tratada de forma idêntica à desconexão voluntária.

6. Estrutura do Projeto
escape-room/
├── server.py          # Servidor TCP principal
├── client.py          # Cliente CLI
├── game/
│   ├── __init__.py
│   ├── protocol.py    # Constantes, serialização e builders do ERP/1.0
│   ├── rooms.py       # Definição das salas, objetos e enigmas
│   └── state.py       # Gerenciamento de estado da partida
└── README.md

game/protocol.py — define todas as constantes do protocolo (tipos de mensagem, estados, códigos de erro, limites), as funções encode/decode para serialização JSON, e builders para cada tipo de mensagem.
game/rooms.py — define as 3 salas do jogo com seus objetos, descrições narrativas, enigmas encadeados, saídas (trancadas ou abertas) e dicas progressivas.
game/state.py — processa cada comando de jogo (examinar, pegar, usar, ir, inventario, dica), aplica efeitos sobre o estado das salas e dos jogadores, e detecta a condição de vitória.
server.py — aceita conexões TCP, cria uma thread por cliente, protege o estado compartilhado com threading.Lock, gerencia o ciclo completo de uma partida (lobby → countdown → jogo → game over → reset).
client.py — conecta ao servidor, envia JOIN com o username, usa uma thread dedicada para receber e renderizar mensagens do servidor em tempo real enquanto o jogador digita comandos no terminal.

7. Comandos do Jogo
Comando
Exemplo
Descrição
examinar <objeto>
examinar mesa
Descreve o objeto em detalhe. Pode revelar objetos ocultos.
pegar <objeto>
pegar chave_vermelha
Adiciona o objeto ao inventário do jogador.
usar <item> em <objeto>
usar chave_azul em porta_leste
Combina um item do inventário com um objeto da sala.
ir <direção>
ir leste
Move para a sala adjacente (norte, sul, leste, oeste).
inventario
inventario
Lista os itens que o jogador carrega.
dica
dica
Solicita a próxima dica para a sala atual (progressiva).
chat <mensagem>
chat Achei a chave!
Envia mensagem para todos os jogadores.
READY
READY
No lobby: sinaliza que o jogador está pronto para iniciar.
sair
sair
Desconecta voluntariamente do servidor.


8. Salas e Enigmas
O jogo possui 3 salas encadeadas. A progressão exige colaboração entre os jogadores, pois pistas de uma sala podem ser necessárias para resolver enigmas de outra.
Sala 1 — Laboratório Abandonado
Sala inicial. Contém uma mesa, um cofre de 4 dígitos, um quadro-negro com uma sequência numérica incompleta e uma lixeira com uma anotação. O objetivo é descobrir o código do cofre, obter a chave azul e destrancar a saída leste.
Sala 2 — Corredor
Acessível após resolver o laboratório. Contém fotografias com instruções e uma caixa de fusíveis com uma peça faltando. A peça está escondida sob um tapete. Encaixar o fusível correto destranca a porta norte.
Sala 3 — Sala Final
Acessível após o corredor. Contém um terminal de computador que exige uma senha mestre. A senha está codificada em uma placa na parede e confirmada em um diário aberto. Inserir a senha correta no terminal abre a saída principal e encerra o jogo com vitória.


