# Escape Room Cooperativo — ERP/1.0

Projeto final da disciplina de Redes de Computadores I.

**Alunos:** Arthur Araújo, Bruno Cardoso, João Pedro França e Lucas Vieira  
**Aplicação:** jogo cooperativo de Escape Room em terminal, para 2 a 4 jogadores, usando arquitetura cliente-servidor, sockets TCP e um protocolo de aplicação próprio: **ERP/1.0 — Escape Room Protocol**.

---

## Sumário

1. [Descrição geral](#1-descrição-geral)
2. [Arquitetura da solução](#2-arquitetura-da-solução)
3. [Motivação da escolha do TCP](#3-motivação-da-escolha-do-tcp)
4. [Requisitos mínimos](#4-requisitos-mínimos)
5. [Como executar](#5-como-executar)
6. [Funcionamento do jogo](#6-funcionamento-do-jogo)
7. [Normalização e facilitação da digitação](#7-normalização-e-facilitação-da-digitação)
8. [Robustez contra desconexões e anti-softlock](#8-robustez-contra-desconexões-e-anti-softlock)
9. [Protocolo ERP/1.0](#9-protocolo-erp10)
10. [Broadcast, unicast e chat](#10-broadcast-unicast-e-chat)
11. [Subprotocolo de descoberta por UDP broadcast](#11-subprotocolo-de-descoberta-por-udp-broadcast)
12. [Fluxo resumido da partida](#12-fluxo-resumido-da-partida)
13. [Concorrência e consistência](#13-concorrência-e-consistência)
14. [Limitações conhecidas](#14-limitações-conhecidas)

---

## 1. Descrição geral

A aplicação implementa um **Escape Room cooperativo em rede local**. Entre 2 e 4 jogadores entram na mesma partida, são distribuídos entre dois caminhos diferentes do mapa e precisam colaborar para resolver enigmas, compartilhar pistas pelo chat e escapar dentro do tempo limite.

O objetivo didático é aplicar conceitos de Redes de Computadores, especialmente:

- comunicação cliente-servidor;
- sockets TCP;
- definição de protocolo de aplicação;
- serialização de mensagens em JSON;
- máquina de estados do servidor;
- concorrência com múltiplos clientes;
- sincronização de estado compartilhado;
- tolerância a desconexões e quedas de rede.

O servidor é a **fonte única de verdade** da partida. Ele mantém o estado global do jogo: jogadores, salas, objetos, inventários, enigmas, tempo restante, condição de vitória e condição de derrota. Os clientes não alteram o estado diretamente; eles apenas enviam comandos e recebem as atualizações calculadas pelo servidor.

---

## 2. Arquitetura da solução

A solução é organizada nos seguintes arquivos:

| Arquivo | Responsabilidade |
|---|---|
| `server.py` | Servidor TCP. Aceita conexões, mantém a máquina de estados da partida, processa mensagens e decide quais clientes recebem quais respostas. |
| `client.py` | Cliente de terminal. Envia comandos do jogador e renderiza mensagens recebidas do servidor. |
| `launcher.py` | Menu de conveniência. Permite criar uma partida ou entrar em uma partida existente usando descoberta automática por UDP broadcast. |
| `game/protocol.py` | Define tipos de mensagens, estados do servidor, códigos de erro e funções de serialização/desserialização. |
| `game/state.py` | Implementa a lógica do jogo: jogadores, salas, inventário, comandos, enigmas, movimentação, aliases e anti-softlock. |
| `game/rooms.py` | Define o mapa jogável atual: Hospital Abandonado. |

O servidor usa uma arquitetura **single-process e multi-thread**: a thread principal aceita conexões (`accept`) e cria uma thread dedicada para cada cliente conectado. Todas as threads acessam o mesmo estado global (`GameState`), então o servidor usa `threading.Lock` para serializar operações sensíveis, como `JOIN`, `ACTION` e desconexões.

---

## 3. Motivação da escolha do TCP

O protocolo principal do jogo, ERP/1.0, roda sobre **TCP**.

Essa escolha foi feita porque o jogo depende de uma máquina de estados compartilhada. Uma ação como `pegar chave_direita` só faz sentido se o servidor já tiver processado, na ordem correta, as ações anteriores que permitiram ao jogador chegar até aquela sala e visualizar aquele item.

O TCP oferece características importantes para esse cenário:

### 3.1. Entrega confiável

O TCP garante que os dados enviados sejam entregues ou que a conexão seja considerada quebrada. Isso evita que mensagens importantes, como `ACTION`, `ROOM_UPDATE` ou `GAME_OVER`, desapareçam silenciosamente.

### 3.2. Ordem de chegada

As mensagens chegam na mesma ordem em que foram enviadas. Isso é essencial para não corromper o estado do jogo. Por exemplo, o servidor precisa processar `ir leste` antes de `pegar chave`, caso a chave esteja na sala de destino.

### 3.3. Conexão persistente

Cada jogador mantém uma conexão TCP aberta com o servidor durante a partida. Isso simplifica a identificação de qual cliente enviou cada comando.

### 3.4. Delimitação de mensagens com JSON + `\n`

O TCP entrega um fluxo contínuo de bytes, sem preservar fronteiras de mensagem. Por isso, o ERP/1.0 usa uma estratégia de enquadramento: cada mensagem é um objeto JSON finalizado por uma quebra de linha (`\n`).

Exemplo:

```json
{"type": "ACTION", "payload": {"command": "examinar mesa"}}
```

O servidor e o cliente acumulam bytes em um buffer e só decodificam uma mensagem quando encontram `\n`. Isso permite reconstruir corretamente mensagens mesmo que o TCP entregue dados fragmentados ou agrupados.

---

## 4. Requisitos mínimos

- Python 3.10 ou superior.
- Rede TCP/IP entre as máquinas.
- Porta TCP `5000` liberada no host do servidor.
- Terminal com suporte a UTF-8.
- Entre 2 e 4 jogadores.

### Observação sobre Windows e `readline`

O cliente importa o módulo `readline` para melhorar a experiência visual do terminal, preservando melhor o texto que o jogador está digitando quando chegam mensagens do servidor.

Em Linux e macOS, esse módulo geralmente já vem disponível. No Windows, pode aparecer:

```text
ModuleNotFoundError: No module named 'readline'
```

Nesse caso, instale:

```powershell
python -m pip install pyreadline3
```

ou:

```powershell
py -m pip install pyreadline3
```

Depois rode novamente:

```powershell
python launcher.py
```

---

## 5. Como executar

## 5.1. Forma recomendada: `launcher.py`

A forma mais simples para apresentação é usar o `launcher.py`.

No computador que será o host:

```bash
python3 launcher.py
```

Escolha:

```text
1. Criar partida
```

Esse computador inicia o servidor TCP e também entra como jogador local.

Nos outros computadores:

```bash
python3 launcher.py
```

Escolha:

```text
2. Entrar em partida
```

O launcher procura automaticamente um servidor na rede usando UDP broadcast. Se encontrar, conecta sozinho. Se não encontrar, pede o IP manualmente.

## 5.2. Forma manual

No computador servidor:

```bash
python3 server.py
```

Nos computadores clientes:

```bash
python3 client.py --host IP_DO_SERVIDOR
```

Exemplo:

```bash
python3 client.py --host 192.168.0.10
```

Para testar tudo na mesma máquina:

```bash
python3 client.py --host 127.0.0.1
```

## 5.3. Escolha de nome do jogador

Ao abrir o cliente, o jogador informa um nome.

Se o nome já estiver em uso, o servidor responde:

```text
ERROR [NAME_TAKEN]
```

O cliente então pede outro nome automaticamente, sem precisar fechar e abrir o programa novamente. O loop normal de comandos só começa depois que o servidor aceita o nome e envia `WELCOME`.

---

## 6. Funcionamento do jogo

## 6.1. Quantidade de jogadores

A partida aceita de 2 a 4 jogadores.

As constantes do protocolo são:

```text
MIN_PLAYERS = 2
MAX_PLAYERS = 4
```

## 6.2. Papéis e caminhos essenciais

O mapa atual, **Hospital Abandonado**, possui dois caminhos essenciais:

- `role 0`: caminho da Recepção;
- `role 1`: caminho da Sala de Força.

Os jogadores são distribuídos de forma alternada:

```text
2 jogadores → role 0, role 1
3 jogadores → role 0, role 1, role 0
4 jogadores → role 0, role 1, role 0, role 1
```

Com isso, jogadores extras entram como apoio em caminhos já existentes. O mapa não cria `role 2` ou `role 3`; ele redistribui os jogadores entre os dois papéis essenciais.

## 6.3. Cooperação entre caminhos

Os caminhos são separados inicialmente, mas dependem um do outro.

Exemplo: o jogador da Sala de Força pode encontrar uma informação necessária para o jogador da Recepção. Por isso, o chat faz parte da mecânica principal do jogo.

O jogo não anuncia automaticamente todo item encontrado. Se um jogador descobrir uma senha, pista ou item importante, ele deve comunicar pelo chat:

```text
chat Achei a senha do cofre: 9999
```

Alguns eventos críticos são anunciados automaticamente pelo servidor via `PLAYER_EVENT`, como energia religada, porta liberada remotamente ou reencontro dos jogadores no corredor central.

## 6.4. Mapa atual: Hospital Abandonado

### Caminho da Recepção — `role 0`

- Recepção;
- Consultório;
- Ala Médica;
- Corredor Central.

### Caminho da Sala de Força — `role 1`

- Sala de Força;
- Almoxarifado;
- Subsolo;
- Corredor Central.

A saída final fica no Corredor Central e exige duas chaves distintas: uma de cada caminho.

---

## 7. Normalização e facilitação da digitação

Uma das preocupações da aplicação é tornar a interação em terminal mais confortável. O jogador não precisa decorar os nomes internos dos objetos no código nem digitar exatamente com underline.

O motor de comandos aplica uma etapa de **normalização de entrada** antes de interpretar a ação.

## 7.1. Normalização textual

O método de normalização:

- converte o texto para minúsculas;
- remove acentos;
- trata underline (`_`) como espaço;
- trata hífen (`-`) como espaço;
- reduz múltiplos espaços para um único espaço.

Por isso, entradas como estas são equivalentes:

```text
inventario
Inventário
INVENTARIO
```

Também são equivalentes:

```text
porta_leste
porta-leste
porta leste
```

## 7.2. Nomes internos com espaços

Como underlines são tratados como espaços, o jogador pode digitar nomes de objetos de forma mais natural.

Exemplos:

| Entrada do jogador | Objeto interno correspondente |
|---|---|
| `placa de alimentacao` | `placa_de_alimentacao` |
| `caixa de ferramentas` | `caixa_de_ferramentas` |
| `dispositivo esquerdo` | `dispositivo_esquerdo` |
| `dispositivo direito` | `dispositivo_direito` |
| `porta leste` | `porta_leste` |
| `porta sul` | `porta_sul` |

## 7.3. Aliases de objetos

Além da normalização, o jogo possui aliases para objetos importantes. Isso permite que o jogador use nomes curtos.

| Entrada curta | Objeto interno |
|---|---|
| `terminal` | `terminal_de_monitoramento` |
| `painel` | `painel_de_controle` |
| `cofre` | `cofre_medico` |
| `caixa` | `caixa_de_ferramentas` |
| `servidor` | `servidor_de_ti` |
| `porta norte` | `porta_norte` |
| `porta leste` | `porta_leste` |
| `porta sul` | `porta_sul` |

Esses aliases respeitam o contexto do jogo. O comando só funciona se o objeto estiver na sala atual do jogador e se o jogador tiver o papel que permite visualizar aquele objeto.

Exemplos:

```text
examinar terminal
```

funciona na Recepção para o jogador que consegue ver o `terminal_de_monitoramento`.

```text
colocar 440 no painel
```

funciona na Sala de Força para o jogador que consegue ver o `painel_de_controle`.

## 7.4. Alias contextual para `porta`

Em algumas salas, existe apenas uma porta interativa visível. Por isso, o jogo aceita o alvo genérico `porta` em comandos de senha.

Exemplos:

```text
colocar 8520 na porta
colocar 1968 na porta
```

Na Recepção, `porta` é resolvida como `porta_leste`.

Na Sala de Força, `porta` é resolvida como `porta_sul`.

Assim, o jogador não precisa saber o nome interno exato da porta.

## 7.5. Exemplos reais de comandos aceitos

| Comando | Observação |
|---|---|
| `examinar terminal` | Funciona na Recepção. |
| `colocar 440 no painel` | Funciona na Sala de Força. |
| `colocar 8520 na porta` | Resolve para `porta_leste` na Recepção. |
| `colocar 1968 na porta` | Resolve para `porta_sul` na Sala de Força. |
| `examinar cofre` | Resolve para `cofre_medico` na Ala Médica. |
| `colocar 9999 no cofre` | Usa o alias do cofre. |
| `examinar servidor` | Resolve para `servidor_de_ti` no Subsolo. |
| `colocar 7701 no servidor` | Usa o alias do servidor. |
| `examinar caixa` | Resolve para `caixa_de_ferramentas`. |
| `colocar 1234 na caixa` | Usa o alias da caixa. |
| `colocar 314 na valvula` | Acento opcional: `válvula` também é aceito. |

---

## 8. Robustez contra desconexões e anti-softlock

Como o mapa depende dos dois papéis essenciais, o servidor trata desconexões com regras específicas.

## 8.1. Desconexão no lobby

Se um jogador sai no lobby, o servidor:

1. remove o jogador;
2. remove o voto de mapa dele;
3. redistribui os papéis dos jogadores restantes;
4. limpa o estado `ready`;
5. envia `LOBBY_UPDATE` e `MAP_VOTE_STATE`.

Isso evita que a partida comece com dois jogadores no mesmo role e nenhum jogador no outro.

## 8.2. Desconexão durante o COUNTDOWN

Se alguém sai durante a contagem regressiva, o servidor verifica:

- se ainda existem pelo menos 2 jogadores;
- se todos os papéis essenciais ainda estão preenchidos;
- se todos os jogadores restantes ainda estão prontos.

Se uma dessas condições falhar, o `COUNTDOWN` é cancelado, o mapa é resetado e os jogadores voltam para o lobby.

## 8.3. Desconexão durante IN_GAME

Durante a partida, há três casos:

### Caso 1 — Restaram menos de 2 jogadores

O jogo termina em derrota com `GAME_OVER`.

### Caso 2 — Um papel essencial ficou vazio

A partida é reiniciada automaticamente:

- mapa resetado;
- inventários limpos;
- papéis redistribuídos;
- jogadores restantes voltam ao lobby;
- todos precisam enviar `ready` de novo.

### Caso 3 — O jogo pode continuar

Se o papel do jogador que caiu ainda estiver coberto por outro jogador, a partida continua.

Nesse caso, os itens que estavam no inventário do jogador desconectado são devolvidos para a sala onde ele estava. Esses itens ficam visíveis e pegáveis por outro jogador do mesmo caminho.

Exemplo:

```text
Bruno estava com chave_direita.
Bruno caiu.
Daniel ainda cobre o role 1.
A partida continua.
chave_direita volta para o chão da sala onde Bruno caiu.
Daniel pode usar: pegar chave direita.
```

Após isso, o servidor envia `ROOM_UPDATE` aos jogadores que permaneceram naquela sala, atualizando a lista de presentes e os objetos disponíveis.

Essa lógica evita softlock, isto é, evita que a partida continue rodando sem ser possível vencê-la.

---

## 9. Protocolo ERP/1.0

## 9.1. Formato geral

Toda mensagem ERP/1.0 é um objeto JSON com dois campos obrigatórios:

```json
{
  "type": "TIPO_DA_MENSAGEM",
  "payload": {}
}
```

Cada mensagem é codificada em UTF-8 e finalizada por `\n`.

## 9.2. Estados do servidor

| Estado | Significado |
|---|---|
| `WAITING_PLAYERS` | Lobby. Permite `JOIN`, `READY` e `MAP_VOTE`. |
| `COUNTDOWN` | Contagem regressiva antes da partida. Não permite novos jogadores. |
| `IN_GAME` | Partida em andamento. Permite `ACTION` e `CHAT`. |
| `GAME_OVER` | Partida encerrada. Após alguns segundos, o servidor reseta para o lobby. |

## 9.3. Transições principais

```text
WAITING_PLAYERS → COUNTDOWN
quando todos estão prontos e todos os roles essenciais estão preenchidos

COUNTDOWN → IN_GAME
quando a contagem chega a zero

COUNTDOWN → WAITING_PLAYERS
se faltar jogador ou role essencial

IN_GAME → WAITING_PLAYERS
se um role essencial for perdido por desconexão

IN_GAME → GAME_OVER
por vitória, tempo esgotado ou menos de 2 jogadores conectados

GAME_OVER → WAITING_PLAYERS
após reset automático
```

## 9.4. Mensagens cliente → servidor

| Mensagem | Payload | Quando é usada |
|---|---|---|
| `JOIN` | `{"username": str}` | Solicita entrada na partida. |
| `READY` | `{}` | Marca o jogador como pronto. |
| `MAP_VOTE` | `{"map": str}` | Registra voto em mapa. Atualmente existe apenas `hospital`. |
| `ACTION` | `{"command": str}` | Envia comando de jogo. |
| `CHAT` | `{"message": str}` | Envia mensagem de chat. |
| `DISCONNECT` | `{}` | Saída voluntária. |

Qualquer tipo de mensagem desconhecido recebe `ERROR [INVALID_ACTION]`.

Qualquer mensagem que não seja `JOIN`, enviada antes do jogador ter sido aceito, recebe `ERROR [INVALID_ACTION]` com a mensagem:

```text
Envie JOIN antes de qualquer outro comando.
```

## 9.5. Mensagens servidor → cliente

| Mensagem | Envio | Uso |
|---|---|---|
| `WELCOME` | Unicast | Confirma que o `JOIN` foi aceito. |
| `MAP_VOTE_STATE` | Unicast ou broadcast | Mostra votos atuais dos mapas. |
| `MAP_SELECTED` | Broadcast | Informa o mapa escolhido ao final do countdown. |
| `LOBBY_UPDATE` | Broadcast | Atualiza jogadores e prontos no lobby. |
| `COUNTDOWN` | Broadcast | Informa segundos restantes da contagem. |
| `GAME_START` | Unicast | Envia a sala inicial específica de cada jogador. |
| `ACTION_RESULT` | Unicast | Resposta direta ao comando de quem agiu. |
| `ROOM_UPDATE` | Broadcast ou envio por sala | Atualiza objetos, saídas e jogadores presentes. |
| `PLAYER_EVENT` | Broadcast | Informa eventos relevantes da partida. |
| `CHAT_BROADCAST` | Broadcast | Entrega mensagem de chat a todos. |
| `TIMER_UPDATE` | Broadcast | Atualiza o tempo restante. |
| `HINT` | Unicast | Responde ao comando `dica`. |
| `GAME_OVER` | Broadcast | Finaliza a partida. |
| `ERROR` | Unicast | Informa erro ao cliente que causou a rejeição. |

## 9.6. Códigos de erro

| Código | Causa |
|---|---|
| `NAME_TAKEN` | Nome de usuário já está em uso. |
| `GAME_FULL` | Sala já tem 4 jogadores. |
| `GAME_IN_PROGRESS` | Tentativa de entrar quando o servidor não está no lobby. |
| `INVALID_ACTION` | Comando inválido, JSON inválido, mapa inexistente ou tipo desconhecido. |
| `NOT_IN_GAME` | Jogador tentou executar `ACTION` fora de `IN_GAME`. |

---

## 10. Broadcast, unicast e chat

A aplicação usa tanto mensagens **unicast** quanto mensagens **broadcast**.

## 10.1. Unicast

Uma mensagem é unicast quando é enviada apenas para um cliente específico.

Exemplos:

- `WELCOME`: só o jogador que entrou recebe seu `player_id`;
- `GAME_START`: cada jogador recebe sua própria sala inicial;
- `ACTION_RESULT`: normalmente só quem executou o comando recebe o resultado textual;
- `HINT`: só quem pediu a dica recebe a dica;
- `ERROR`: só quem causou o erro recebe a mensagem de erro.

Isso evita vazar informações desnecessárias. Por exemplo, se um jogador examina um objeto em sua sala, apenas ele recebe a descrição detalhada daquele objeto.

## 10.2. Broadcast

Uma mensagem é broadcast quando é enviada para todos os jogadores conectados.

Exemplos:

- `LOBBY_UPDATE`;
- `COUNTDOWN`;
- `MAP_SELECTED`;
- `PLAYER_EVENT`;
- `CHAT_BROADCAST`;
- `TIMER_UPDATE`;
- `GAME_OVER`.

O broadcast é usado quando a informação interessa ao grupo todo ou altera a percepção coletiva da partida.

## 10.3. Chat

O chat é enviado pelo cliente como:

```json
{"type": "CHAT", "payload": {"message": "Achei a senha 1968"}}
```

O servidor transforma isso em:

```json
{"type": "CHAT_BROADCAST", "payload": {"from": "Ana", "message": "Achei a senha 1968"}}
```

O `CHAT_BROADCAST` é enviado a todos os jogadores. Ele é essencial porque o jogo não anuncia automaticamente todas as pistas ou itens encontrados. Assim, a colaboração depende dos jogadores comunicarem suas descobertas.

## 10.4. `ROOM_UPDATE`

`ROOM_UPDATE` é usado quando o estado visível de uma sala muda:

- item foi pego;
- item apareceu;
- porta foi destrancada;
- jogador entrou na sala;
- jogador saiu da sala;
- item foi devolvido ao chão após desconexão.

Em ações gerais, o servidor pode transmitir `ROOM_UPDATE` em broadcast, e o cliente renderiza apenas se o próprio jogador estiver em `players_here`.

Em atualizações mais específicas, como desconexão com itens dropados, o servidor envia `ROOM_UPDATE` apenas para os jogadores que permanecem naquela sala. Nesses casos, a atualização também respeita o `role` do jogador, evitando que um cliente veja objetos que não pertencem ao seu caminho.

---

## 11. Subprotocolo de descoberta por UDP broadcast

O `launcher.py` implementa uma descoberta automática de servidor na rede local usando UDP broadcast.

Esse mecanismo é separado do ERP/1.0. O jogo em si usa TCP; o UDP é usado apenas para localizar automaticamente um host já criado.

## 11.1. Portas usadas

| Porta | Protocolo | Uso |
|---|---|---|
| `5000` | TCP | Comunicação principal do jogo. |
| `5001` | UDP | Descoberta automática de servidor pelo launcher. |

## 11.2. Mensagem de descoberta

O host envia periodicamente a mensagem:

```text
ESCAPE_ROOM_ERP1:<ip_do_servidor>:<porta_tcp_do_jogo>
```

Exemplo:

```text
ESCAPE_ROOM_ERP1:192.168.0.10:5000
```

## 11.3. Criando partida

Quando o jogador escolhe:

```text
1. Criar partida
```

O `launcher.py`:

1. inicia o servidor TCP em `0.0.0.0:5000`;
2. detecta o IP local da máquina;
3. inicia uma thread de UDP broadcast;
4. envia a presença do servidor a cada 2 segundos;
5. abre o cliente local conectado em `127.0.0.1`.

## 11.4. Entrando em partida

Quando o jogador escolhe:

```text
2. Entrar em partida
```

O `launcher.py`:

1. abre um socket UDP na porta `5001`;
2. escuta broadcasts por até 6 segundos;
3. se encontrar uma mensagem `ESCAPE_ROOM_ERP1`, extrai IP e porta;
4. abre o cliente TCP conectado ao servidor encontrado;
5. se não encontrar servidor, pede o IP manualmente.

## 11.5. Por que UDP aqui?

UDP é suficiente para a descoberta porque a mensagem é reenviada periodicamente. Se um pacote for perdido, outro será enviado dois segundos depois.

Além disso, broadcast é uma operação natural em UDP. TCP é orientado a conexão ponto-a-ponto, então não serve para descobrir um servidor cujo IP ainda é desconhecido.

---

## 12. Fluxo resumido da partida

1. O servidor é iniciado.
2. Os clientes se conectam.
3. Cada cliente envia `JOIN`.
4. O servidor responde `WELCOME` se o nome for aceito.
5. O servidor envia `LOBBY_UPDATE`.
6. Jogadores podem votar no mapa com `votar hospital`.
7. Todos enviam `READY`.
8. Se todos os roles essenciais estiverem preenchidos, o servidor inicia `COUNTDOWN`.
9. Ao fim do countdown, o servidor envia `MAP_SELECTED`.
10. O servidor envia `GAME_START` individualmente, com a sala inicial de cada jogador.
11. Jogadores executam comandos por `ACTION`.
12. O servidor responde com `ACTION_RESULT`, `ROOM_UPDATE` e/ou `PLAYER_EVENT`.
13. Jogadores trocam informações por `CHAT` e recebem `CHAT_BROADCAST`.
14. Os caminhos se encontram no Corredor Central.
15. A saída final exige as duas chaves.
16. Ao escapar, o servidor envia `GAME_OVER` com resultado `win`.
17. Após alguns segundos, o servidor reseta para o lobby.

---

## 13. Concorrência e consistência

Cada cliente é atendido por uma thread própria no servidor.

Como todas as threads compartilham:

- `GameState`;
- lista de conexões;
- votos de mapa;
- estado da partida;

as operações críticas são protegidas por `threading.Lock`.

Isso impede que duas ações concorrentes corrompam o estado. Por exemplo, se dois jogadores tentarem pegar o mesmo item ao mesmo tempo, o servidor processa uma ação por vez. Depois que o primeiro jogador pega o item, o objeto deixa de estar disponível; o segundo jogador já recebe uma resposta coerente com o estado atualizado.

---

## 14. Limitações conhecidas

## 14.1. Apenas um mapa jogável

O protocolo já possui mensagens de votação de mapa (`MAP_VOTE`, `MAP_VOTE_STATE`, `MAP_SELECTED`), mas atualmente só existe um mapa implementado:

```text
hospital
```

A estrutura foi deixada genérica para permitir novos mapas no futuro.

## 14.2. Descoberta automática limitada à LAN

A auto-descoberta por UDP broadcast funciona apenas no mesmo segmento de rede local. Em redes com isolamento de clientes, VPN, firewall restritivo ou múltiplas sub-redes, pode ser necessário usar o modo manual informando o IP do servidor.

## 14.3. Segundo JOIN em cliente mal-comportado

O cliente oficial só envia `JOIN` repetidamente durante o fluxo de nome já usado, antes de receber `WELCOME`.

Entretanto, do ponto de vista do servidor, um cliente mal-comportado que enviasse manualmente um segundo `JOIN` válido depois de já autenticado poderia registrar um jogador extra compartilhando o mesmo socket. Esse caso não ocorre no cliente de referência, mas é uma limitação conhecida do handler de `JOIN`.

---

## 15. Comandos úteis para apresentação

### Iniciar pelo launcher

```bash
python3 launcher.py
```

### Iniciar manualmente o servidor

```bash
python3 server.py
```

### Entrar manualmente como cliente

```bash
python3 client.py --host 127.0.0.1
```

ou:

```bash
python3 client.py --host IP_DO_SERVIDOR
```

### Comandos de jogo

```text
ready
votar hospital
olhar
inventario
dica
chat <mensagem>
examinar <objeto>
pegar <objeto>
usar <item> em <objeto>
colocar <senha> no <objeto>
ir norte
ir sul
ir leste
ir oeste
sair
```
