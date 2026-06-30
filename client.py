#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Cliente do Escape Room
#  Uso: python3 client.py [--host HOST] [--port PORT]
# ─────────────────────────────────────────────────────────────────
import socket
import threading
import sys
import argparse
import readline

from game.protocol import (
    ServerMsg, decode,
    make_join, make_ready, make_action, make_chat, make_disconnect, make_map_vote,
)

HOST = "127.0.0.1"
PORT = 5000
PROMPT = "> "

MY_USERNAME: str | None = None

# ── Controle do input atual (para não perder o que o usuário digita) ──
_current_input = ""
_input_lock    = threading.Lock()

def print_msg(text: str):
    """
    Imprime mensagem sem sobrescrever o que o usuário está digitando.
    Apaga a linha, imprime a mensagem e reexibe o prompt + input atual.
    """
    with _input_lock:
        sys.stdout.write("\r\033[K")
        print(text)
        sys.stdout.write(PROMPT + _current_input)
        sys.stdout.flush()


# ── Renderizadores por tipo de mensagem ──────────────────────────

def render(msg_type: str, payload: dict):

    if msg_type == ServerMsg.WELCOME:
        print_msg(
            f"\n{'═'*56}\n"
            f"  Bem-vindo(a)! ID: {payload['player_id']}\n"
            f"  Estado: {payload['server_state']}\n"
            f"  Aguardando jogadores... Digite READY quando pronto.\n"
            f"  Para votar no mapa: votar hospital\n"
            f"{'═'*56}"
        )

    elif msg_type == ServerMsg.MAP_VOTE_STATE:
        votes = payload.get("votes", {})
        maps  = payload.get("maps", {})
        lines = ["\n┌─ Votação de Mapa ──────────────────────────────────"]
        for map_key, map_name in maps.items():
            v   = votes.get(map_key, 0)
            bar = "█" * v + "░" * (3 - v)
            lines.append(f"│  [{v}] {bar}  {map_name}")
            lines.append(f"│       → digite: votar {map_key}")
        lines.append("└" + "─"*52)
        print_msg("\n".join(lines))

    elif msg_type == ServerMsg.MAP_SELECTED:
        map_name = payload.get("map_name", "")
        print_msg(f"\n🗺️  Mapa selecionado: {map_name}\n")

    elif msg_type == ServerMsg.LOBBY_UPDATE:
        players = payload.get("players", [])
        ready   = payload.get("ready_count", 0)
        total   = payload.get("total", 0)
        lines   = [f"\n┌─ Lobby ({ready}/{total} prontos) {'─'*30}"]
        for p in players:
            status = "✔ pronto   " if p["ready"] else "⋯ aguardando"
            lines.append(f"│  {status}  {p['username']}")
        lines.append("└" + "─"*48)
        print_msg("\n".join(lines))

    elif msg_type == ServerMsg.COUNTDOWN:
        secs = payload.get("seconds", 0)
        print_msg(f"  ⏳ O jogo começa em {secs}s...")

    elif msg_type == ServerMsg.GAME_START:
        room  = payload.get("room", "")
        desc  = payload.get("description", "")
        limit = payload.get("time_limit", 0)
        mins  = limit // 60
        print_msg(
            f"\n{'╔'+'═'*54+'╗'}\n"
            f"║{'  🚪 ESCAPE ROOM — JOGO INICIADO!':^54}║\n"
            f"{'╚'+'═'*54+'╝'}\n"
            f"\n📍 Sala inicial: {room}\n"
            f"⏱  Tempo limite: {mins} minutos\n\n"
            f"{desc}\n\n"
            f"Comandos disponíveis:\n"
            f"  examinar <obj>          · pegar <obj>\n"
            f"  usar <item> em <obj>    · colocar <valor> no <obj>\n"
            f"  ir <norte|sul|leste|oeste>\n"
            f"  inventario · dica · chat <msg>\n"
            f"{'─'*56}"
        )

    elif msg_type == ServerMsg.ACTION_RESULT:
        ok  = payload.get("success", False)
        msg = payload.get("message", "")
        if "__ESCAPED__" in msg:
            return
        icon = "✅" if ok else "❌"
        print_msg(f"{icon} {msg}")

    elif msg_type == ServerMsg.ROOM_UPDATE:
        state   = payload.get("room_state", {})
        objects = payload.get("objects", [])
        here    = payload.get("players_here", [])
        exits   = state.get("exits", {})
        room    = state.get("name", "")

        # Só renderiza a sala em que o jogador está presente
        if MY_USERNAME and MY_USERNAME not in here:
            return

        sep = "─" * max(0, 48 - len(room))
        exit_lines = []
        for direction, info in exits.items():
            icon = "🔒" if info.get("locked") else "🔓"
            exit_lines.append(f"│    {icon} {direction} → {info.get('room','?')}")

        print_msg(
            f"\n┌─ {room} {sep}\n"
            f"│  Objetos: {', '.join(objects) if objects else '(nenhum)'}\n"
            f"│  Saídas:\n" +
            "\n".join(exit_lines) + "\n"
            f"│  Jogadores aqui: {', '.join(here)}\n"
            f"└{'─'*52}"
        )

    elif msg_type == ServerMsg.CHAT_BROADCAST:
        sender = payload.get("from", "?")
        msg    = payload.get("message", "")
        print_msg(f"💬 [{sender}]: {msg}")

    elif msg_type == ServerMsg.TIMER_UPDATE:
        rem  = payload.get("remaining", 0)
        mins = rem // 60
        secs = rem % 60
        warn = " ⚠️ " if rem <= 60 else " "
        print_msg(f"⏱{warn}Tempo restante: {mins}m {secs:02d}s")

    elif msg_type == ServerMsg.PLAYER_EVENT:
        event  = payload.get("event", "")
        detail = payload.get("detail", "")
        icons  = {
            "joined":             "➕",
            "left":               "➖",
            "moved":              "🚶",
            "found":              "🔎",
            "solved":             "🧩",
            "countdown_cancelled":"⏹",
            "match_reset":        "🔄",
        }
        print_msg(f"{icons.get(event, '•')} {detail}")

    elif msg_type == ServerMsg.HINT:
        print_msg(f"\n💡 DICA: {payload.get('text', '')}\n")

    elif msg_type == ServerMsg.GAME_OVER:
        result  = payload.get("result", "")
        elapsed = payload.get("time_elapsed", 0)
        msg     = payload.get("message", "")
        banner  = "🏆  VITÓRIA!" if result == "win" else "💀  DERROTA"
        mins    = elapsed // 60
        secs    = elapsed % 60
        print_msg(
            f"\n{'╔'+'═'*54+'╗'}\n"
            f"║{banner:^54}║\n"
            f"{'╚'+'═'*54+'╝'}\n"
            f"  {msg}\n"
            f"  Tempo decorrido: {mins}m {secs:02d}s\n"
            f"\n  Nova partida em 10 segundos...\n"
        )

    elif msg_type == ServerMsg.ERROR:
        code = payload.get("code", "")
        msg  = payload.get("message", "")
        print_msg(f"⚠️  ERRO [{code}]: {msg}")


# ── Thread de recepção ───────────────────────────────────────────

def receive_loop(sock: socket.socket, stop_event: threading.Event):
    buf = ""
    while not stop_event.is_set():
        try:
            data = sock.recv(4096)
        except OSError:
            break
        if not data:
            print_msg("\n[Servidor encerrou a conexão]")
            stop_event.set()
            break
        buf += data.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if line.strip():
                try:
                    msg_type, payload = decode(line)
                    render(msg_type, payload)
                except Exception as e:
                    print_msg(f"[ERRO ao processar mensagem]: {e}")


# ── Loop de entrada ──────────────────────────────────────────────

def input_loop(sock: socket.socket, stop_event: threading.Event):
    global _current_input

    # Rastreia o que o usuário está digitando para reexibir após mensagens
    def pre_input_hook():
        global _current_input
        with _input_lock:
            _current_input = readline.get_line_buffer()

    readline.set_pre_input_hook(pre_input_hook)
    sys.stdout.write(PROMPT)
    sys.stdout.flush()

    while not stop_event.is_set():
        try:
            raw = input()
            with _input_lock:
                _current_input = ""
            raw = raw.strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            sys.stdout.write(PROMPT)
            sys.stdout.flush()
            continue

        lower = raw.lower()

        try:
            if lower in ("sair", "quit"):
                sock.sendall(make_disconnect())
                break

            elif lower == "ready":
                sock.sendall(make_ready())

            elif lower.startswith("votar "):
                map_key = raw[6:].strip().lower()
                sock.sendall(make_map_vote(map_key))

            elif lower.startswith("chat "):
                msg = raw[5:].strip()
                if msg:
                    sock.sendall(make_chat(msg))

            else:
                sock.sendall(make_action(raw))

        except OSError:
            break

        sys.stdout.write(PROMPT)
        sys.stdout.flush()

    stop_event.set()


# ── Bootstrap ────────────────────────────────────────────────────

def main():
    global MY_USERNAME

    parser = argparse.ArgumentParser(description="ERP/1.0 Escape Room Client")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    args = parser.parse_args()

    print(f"{'═'*56}")
    print(f"  🚪 ESCAPE ROOM — {args.host}:{args.port}")
    print(f"{'═'*56}")

    username = input("  Seu nome: ").strip()
    while not username:
        username = input("  Nome não pode ser vazio: ").strip()

    MY_USERNAME = username

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((args.host, args.port))
    except ConnectionRefusedError:
        print(f"❌ Não foi possível conectar. Servidor está rodando?")
        sys.exit(1)

    sock.sendall(make_join(username))

    stop_event  = threading.Event()
    recv_thread = threading.Thread(target=receive_loop, args=(sock, stop_event), daemon=True)
    recv_thread.start()

    try:
        input_loop(sock, stop_event)
    finally:
        stop_event.set()
        try:
            sock.close()
        except OSError:
            pass
        print("\n[Desconectado. Até a próxima!]")


if __name__ == "__main__":
    main()
