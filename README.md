# Escape Room — ERP/1.0

Projeto final de Redes de Computadores I: jogo cooperativo de Escape Room em terminal, usando arquitetura cliente-servidor e comunicação via sockets TCP.

## 1. Propósito da aplicação

A aplicação simula um Escape Room cooperativo em rede local. Entre 2 e 4 jogadores entram na mesma partida, recebem papéis/caminhos dentro do mapa e precisam trocar informações pelo chat para resolver enigmas e escapar dentro do tempo limite.

O servidor mantém o estado global do jogo: jogadores, salas, objetos, senhas, portas, eventos, tempo e condição de vitória/derrota. Os clientes enviam comandos e recebem atualizações do servidor.

## 2. Requisitos

- Python 3.10 ou superior.
- Computadores na mesma rede local, caso a partida seja jogada em máquinas diferentes.
- Terminal/console para executar o servidor e os clientes.

## 3. Arquivos principais

- `server.py`: servidor TCP do jogo.
- `client.py`: cliente em terminal.
- `launcher.py`: menu para criar ou entrar em partida com descoberta automática na rede local.
- `game/protocol.py`: tipos de mensagens, formato do protocolo e constantes do jogo.
- `game/state.py`: lógica de estado, comandos, inventário, salas e enigmas.
- `game/rooms.py`: definição do mapa Hospital Abandonado.

## 4. Forma recomendada de rodar: launcher

A forma mais simples para apresentação é usar o `launcher.py`.

### Criar partida

No computador que será o host:

```bash
python3 launcher.py
```

Escolha:

```text
1. Criar partida
```

Esse computador vai iniciar o servidor e também entrar como jogador local.

Além disso, o `launcher.py` começa a transmitir automaticamente a presença do servidor na rede local usando UDP broadcast. Assim, os outros jogadores podem entrar sem digitar o IP manualmente.

### Entrar em partida

Nos computadores dos outros jogadores:

```bash
python3 launcher.py
```

Escolha:

```text
2. Entrar em partida
```

O launcher tentará encontrar automaticamente o servidor na rede. Se encontrar, conecta sozinho. Se não encontrar, ele pedirá o IP manualmente.

## 5. Forma manual de rodar

Também é possível rodar sem launcher.

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

Se estiver testando tudo no mesmo computador, use:

```bash
python3 client.py --host 127.0.0.1
```

## 6. Quantidade de jogadores

A partida aceita de 2 a 4 jogadores.

O mapa atual tem dois papéis/caminhos essenciais:

- `role 0`: caminho da recepção.
- `role 1`: caminho da sala de força.

Os jogadores são distribuídos entre esses papéis. Com 2 jogadores, cada um fica em um caminho. Com 3 ou 4 jogadores, os papéis são alternados:

```text
2 jogadores: role 0, role 1
3 jogadores: role 0, role 1, role 0
4 jogadores: role 0, role 1, role 0, role 1
```

## 7. Regra de desconexão, validação e redistribuição de papéis

O mapa Hospital Abandonado possui dois papéis essenciais: `role 0` e `role 1`. Por isso, não basta ter 2 jogadores conectados: a partida só pode começar ou continuar se todos os papéis essenciais estiverem preenchidos.

Se um jogador sair antes da partida começar, o servidor redistribui os papéis entre os jogadores restantes, limpa o estado de pronto (`ready`) e atualiza o lobby. Isso impede que dois jogadores fiquem, por exemplo, apenas no `role 0`.

Se um jogador sair durante a contagem regressiva e a partida deixar de ter jogadores suficientes ou algum papel essencial ficar sem jogador, o COUNTDOWN é cancelado. O mapa é resetado, os papéis são redistribuídos, todos voltam para o lobby e precisam enviar `ready` novamente.

Se um jogador cair durante a partida e restarem menos de 2 jogadores, o jogo termina com derrota.

Se ainda restarem pelo menos 2 jogadores, mas algum papel essencial ficar sem jogador, a partida é reiniciada automaticamente. Nesse caso:

- o estado do mapa é resetado;
- inventários são limpos;
- os jogadores restantes voltam para o lobby;
- os papéis essenciais são redistribuídos entre os jogadores restantes;
- todos precisam enviar `ready` novamente.

Se o jogador sair durante a partida e o jogo puder continuar, os itens que estavam no inventário dele são devolvidos para a sala onde ele estava. Assim, outro jogador do mesmo caminho pode pegar esses itens sem precisar refazer os puzzles que já tinham sido resolvidos. O servidor também envia `ROOM_UPDATE` para os jogadores que continuaram naquela sala, atualizando a lista de jogadores presentes e os objetos disponíveis.

Após um `GAME_OVER`, o reset automático também redistribui os papéis dos jogadores que continuarem conectados.

Essa regra evita softlock, ou seja, evita que o jogo continue rodando ou comece sem alguém em um caminho obrigatório, e também evita que um item essencial desapareça com um jogador desconectado.

## 8. Comandos do cliente

### Comandos gerais

```text
ready
sair
chat <mensagem>
votar hospital
olhar
sala
inventario
dica
```

### Comandos de ação

```text
examinar <objeto>
pegar <objeto>
usar <item> em <objeto>
colocar <senha> no <objeto>
ir <direção>
```

Direções aceitas:

```text
norte
sul
leste
oeste
```

## 9. Alias contextual para porta

Algumas salas possuem uma única porta interativa. Por isso, o jogo aceita o alvo genérico `porta` quando for possível identificar a porta correta pelo contexto da sala.

Exemplos que funcionam:

```text
colocar 8520 na porta
colocar 1968 na porta
```

Na recepção, `porta` é entendida como `porta_leste`.

Na sala de força, `porta` é entendida como `porta_sul`.

Também continuam funcionando os comandos específicos:

```text
colocar 8520 na porta_leste
colocar 1968 na porta_sul
```

## 10. Colaboração entre jogadores

O jogo não envia evento geral toda vez que alguém encontra um objeto físico escondido. Quando um jogador descobre uma informação ou encontra um item, ele deve avisar os outros pelo chat.

Exemplo:

```text
chat Achei a senha do cofre: 9999
```

Alguns eventos cooperativos importantes ainda são enviados automaticamente pelo servidor, como energia religada, portas liberadas remotamente e reencontro dos jogadores.

## 11. Mapa atual: Hospital Abandonado

O mapa possui dois caminhos principais.

### Caminho da recepção

- Recepção.
- Consultório.
- Ala médica.
- Corredor central.

### Caminho da sala de força

- Sala de força.
- Almoxarifado.
- Subsolo.
- Corredor central.

Os caminhos dependem um do outro. Um jogador encontra pistas que o outro precisa usar, por isso o chat é parte essencial da cooperação.

## 12. Fluxo resumido da partida

1. O servidor é iniciado.
2. Os clientes entram na partida.
3. Os jogadores podem votar no mapa com `votar hospital`.
4. Todos digitam `ready`.
5. O servidor inicia o COUNTDOWN.
6. A partida começa.
7. Cada jogador recebe sua sala inicial de acordo com o papel.
8. Os jogadores resolvem enigmas e trocam informações pelo chat.
9. Os caminhos se encontram no corredor central.
10. A saída final exige as duas chaves.
11. Ao escapar, o servidor envia GAME_OVER com vitória.

## 13. Protocolo de aplicação

O protocolo ERP/1.0 usa mensagens JSON finalizadas por quebra de linha (`\n`).

Exemplo geral:

```json
{
  "type": "ACTION",
  "payload": {
    "command": "examinar mesa"
  }
}
```

Principais mensagens cliente → servidor:

- `JOIN`
- `READY`
- `MAP_VOTE`
- `ACTION`
- `CHAT`
- `DISCONNECT`

Principais mensagens servidor → cliente:

- `WELCOME`
- `LOBBY_UPDATE`
- `MAP_VOTE_STATE`
- `MAP_SELECTED`
- `COUNTDOWN`
- `GAME_START`
- `ACTION_RESULT`
- `ROOM_UPDATE`
- `PLAYER_EVENT`
- `CHAT_BROADCAST`
- `TIMER_UPDATE`
- `HINT`
- `GAME_OVER`
- `ERROR`

## 14. Observações para apresentação

- Rodar pelo `launcher.py` facilita a conexão em rede local.
- Caso a descoberta automática não funcione, usar o modo manual informando o IP do servidor.
- O jogo depende de comunicação via chat: se alguém achar uma senha ou pista, precisa avisar os outros jogadores.
- Se um jogador essencial cair, a partida é reiniciada e os papéis são redistribuídos para impedir que o jogo fique impossível de concluir.
