#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Cliente do Escape Room
#  Uso: python client.py [--host HOST] [--port PORT]
# ─────────────────────────────────────────────────────────────────
import socket
import threading
import sys
import argparse
import json

from game.protocol import (
    ServerMsg, decode,
    make_join, make_ready, make_action, make_chat, make_disconnect,
)

HOST = "127.0.0.1"
PORT = 5000

# ── Helpers de exibição ──────────────────────────────────────────

def clear_line():
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

def print_msg(text: str):
    """Imprime uma linha acima do prompt atual."""
    clear_line()
    print(text)
    sys.stdout.write(PROMPT)
    sys.stdout.flush()

PROMPT = "\n> "
MY_USERNAME: str | None = None


# ── Renderizadores por tipo de mensagem ──────────────────────────

def render(msg_type: str, payload: dict):
    """Formata e imprime cada tipo de mensagem recebida do servidor."""

    if msg_type == ServerMsg.WELCOME:
        print_msg(
            f"\n{'═'*54}\n"
            f"  Bem-vindo(a)! ID: {payload['player_id']}\n"
            f"  Estado do servidor: {payload['server_state']}\n"
            f"  Aguardando outros jogadores...\n"
            f"  Digite READY quando estiver pronto.\n"
            f"{'═'*54}"
        )

    elif msg_type == ServerMsg.LOBBY_UPDATE:
        players = payload.get("players", [])
        ready   = payload.get("ready_count", 0)
        total   = payload.get("total", 0)
        lines   = [f"\n┌─ Lobby ({ready}/{total} prontos) ─────────────────────"]
        for p in players:
            status = "✔ pronto   " if p["ready"] else "⋯ aguardando"
            lines.append(f"│  {status}  {p['username']}")
        lines.append("└────────────────────────────────────────────────")
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
            f"\n{'╔'+'═'*52+'╗'}\n"
            f"║{'  🚪 ESCAPE ROOM — JOGO INICIADO!':^52}║\n"
            f"{'╚'+'═'*52+'╝'}\n"
            f"\n📍 Sala: {room}\n"
            f"⏱  Tempo limite: {mins} minutos\n\n"
            f"{desc}\n\n"
            f"Comandos: examinar <obj> · pegar <obj> · usar <item> em <obj>\n"
            f"          ir <norte|sul|leste|oeste> · inventario · dica · chat <msg>\n"
            f"{'─'*54}"
        )

    elif msg_type == ServerMsg.ACTION_RESULT:
        ok  = payload.get("success", False)
        msg = payload.get("message", "")
        if "__ESCAPED__" in msg:
            return  # GAME_OVER vai cuidar disso
        icon = "✅" if ok else "❌"
        print_msg(f"{icon} {msg}")

    elif msg_type == ServerMsg.ROOM_UPDATE:
        state   = payload.get("room_state", {})
        objects = payload.get("objects", [])
        here    = payload.get("players_here", [])
        exits   = state.get("exits", {})
        room    = state.get("name", "")

        # O servidor pode enviar ROOM_UPDATE em broadcast, mas o cliente
        # só deve renderizar o estado detalhado da sala onde ele está.
        # Assim ninguém vê objetos/saídas de salas em que não está presente.
        if MY_USERNAME and MY_USERNAME not in here:
            return

        exit_lines = []
        for direction, info in exits.items():
            lock_icon = "🔒" if info.get("locked") else "🔓"
            exit_lines.append(f"    {lock_icon} {direction} → {info.get('room','?')}")

        print_msg(
            f"\n┌─ {room} {'─'*(46-len(room))}\n"
            f"│  Objetos: {', '.join(objects) if objects else '(nenhum)'}\n"
            f"│  Saídas:\n" +
            "\n".join(f"│  {l}" for l in exit_lines) + "\n"
            f"│  Aqui: {', '.join(here)}\n"
            f"└{'─'*50}"
        )

    elif msg_type == ServerMsg.CHAT_BROADCAST:
        sender = payload.get("from", "?")
        msg    = payload.get("message", "")
        print_msg(f"💬 [{sender}]: {msg}")

    elif msg_type == ServerMsg.TIMER_UPDATE:
        rem  = payload.get("remaining", 0)
        mins = rem // 60
        secs = rem % 60
        warn = " ⚠️ " if rem <= 60 else ""
        print_msg(f"⏱{warn} Tempo restante: {mins}m {secs:02d}s")

    elif msg_type == ServerMsg.PLAYER_EVENT:
        event  = payload.get("event", "")
        detail = payload.get("detail", "")
        icons  = {
            "joined": "➕",
            "left": "➖",
            "moved": "🚶",
            "found": "🔎",
            "solved": "🧩",
            "countdown_cancelled": "⏹",
        }
        icon   = icons.get(event, "•")
        print_msg(f"{icon} {detail}")

    elif msg_type == ServerMsg.HINT:
        text = payload.get("text", "")
        print_msg(f"\n💡 DICA: {text}\n")

    elif msg_type == ServerMsg.GAME_OVER:
        result  = payload.get("result", "")
        elapsed = payload.get("time_elapsed", 0)
        msg     = payload.get("message", "")
        banner  = "🏆  VITÓRIA!" if result == "win" else "💀  DERROTA"
        mins    = elapsed // 60
        secs    = elapsed % 60
        print_msg(
            f"\n{'╔'+'═'*52+'╗'}\n"
            f"║{banner:^52}║\n"
            f"{'╚'+'═'*52+'╝'}\n"
            f"  {msg}\n"
            f"  Tempo decorrido: {mins}m {secs:02d}s\n"
            f"\n  Nova partida começa em 10 segundos...\n"
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


# ── Loop de entrada do usuário ───────────────────────────────────

def input_loop(sock: socket.socket, stop_event: threading.Event):
    """Lê comandos do terminal e os envia para o servidor."""
    while not stop_event.is_set():
        try:
            sys.stdout.write(PROMPT)
            sys.stdout.flush()
            raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        lower = raw.lower()

        # ── Comandos locais ──────────────────────────────────────
        if lower == "sair" or lower == "quit":
            sock.sendall(make_disconnect())
            break

        if lower == "ready":
            sock.sendall(make_ready())
            continue

        # ── Chat: "chat <mensagem>" ──────────────────────────────
        if lower.startswith("chat "):
            msg = raw[5:].strip()
            if msg:
                sock.sendall(make_chat(msg))
            continue

        # ── Qualquer outra coisa é um comando de jogo ────────────
        try:
            sock.sendall(make_action(raw))
        except OSError:
            break

    stop_event.set()


# ── Conexão e bootstrap ──────────────────────────────────────────

def connect(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock


def main():
    global MY_USERNAME

    parser = argparse.ArgumentParser(description="ERP/1.0 Escape Room Client")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    args = parser.parse_args()

    print(f"{'═'*54}")
    print(f"  🚪 ESCAPE ROOM — Conectando em {args.host}:{args.port}")
    print(f"{'═'*54}")

    username = input("  Seu nome: ").strip()
    while not username:
        username = input("  Nome não pode ser vazio. Tente novamente: ").strip()

    MY_USERNAME = username

    try:
        sock = connect(args.host, args.port)
    except ConnectionRefusedError:
        print(f"❌ Não foi possível conectar em {args.host}:{args.port}. Servidor está rodando?")
        sys.exit(1)

    # Envia JOIN imediatamente
    sock.sendall(make_join(username))

    stop_event = threading.Event()

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
