#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Servidor principal do Escape Room
#  Uso: python server.py [--host HOST] [--port PORT]
# ─────────────────────────────────────────────────────────────────
import socket
import threading
import time
import argparse
import uuid
import sys

from game.protocol import (
    State, ClientMsg,
    decode,
    make_welcome, make_lobby_update, make_countdown,
    make_game_start, make_player_event, make_timer_update,
    make_game_over, make_error, make_chat_broadcast,
    ErrorCode, COUNTDOWN_SECONDS, GAME_TIME_LIMIT,
    TIMER_BROADCAST_INTERVAL, CRITICAL_TIME_MARKS,
    MIN_PLAYERS, MAX_PLAYERS,
)
from game.state import GameState

HOST = "0.0.0.0"
PORT = 5000


class Server:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.state      = State.WAITING_PLAYERS
        self.game_state = GameState()
        self.lock       = threading.Lock()          # protege estado compartilhado

        # player_id → socket
        self.connections: dict[str, socket.socket] = {}

        self._timer_thread: threading.Thread | None = None
        self._game_start_time: float = 0.0

    # ── Inicialização ────────────────────────────────────────────

    def start(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(MAX_PLAYERS)
        print(f"[ERP/1.0] Servidor rodando em {self.host}:{self.port}")
        print(f"          Aguardando {MIN_PLAYERS}–{MAX_PLAYERS} jogadores...")

        try:
            while True:
                conn, addr = server_sock.accept()
                print(f"[CONN] Nova conexão de {addr}")
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("\n[ERP/1.0] Servidor encerrado.")
        finally:
            server_sock.close()

    # ── Loop do cliente (uma thread por conexão) ─────────────────

    def _handle_client(self, conn: socket.socket):
        player_id = None
        buf = ""

        try:
            for raw_line in self._readlines(conn):
                try:
                    msg_type, payload = decode(raw_line)
                except (ValueError, Exception) as e:
                    self._send(conn, make_error(ErrorCode.INVALID_ACTION, f"Mensagem inválida: {e}"))
                    continue

                player_id = self._dispatch(conn, player_id, msg_type, payload)

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self._on_disconnect(player_id, conn)

    def _readlines(self, conn: socket.socket):
        """Gerador que emite linhas completas lidas do socket."""
        buf = ""
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if line.strip():
                    yield line

    # ── Dispatcher de mensagens ──────────────────────────────────

    def _dispatch(self, conn: socket.socket, player_id: str | None, msg_type: str, payload: dict) -> str | None:
        """Roteia cada mensagem para o handler correto. Retorna player_id."""

        if msg_type == ClientMsg.JOIN:
            return self._on_join(conn, payload)

        if player_id is None:
            self._send(conn, make_error(ErrorCode.INVALID_ACTION, "Envie JOIN antes de qualquer outro comando."))
            return None

        if msg_type == ClientMsg.READY:
            self._on_ready(player_id)

        elif msg_type == ClientMsg.ACTION:
            self._on_action(player_id, payload.get("command", ""))

        elif msg_type == ClientMsg.CHAT:
            self._on_chat(player_id, payload.get("message", ""))

        elif msg_type == ClientMsg.DISCONNECT:
            raise ConnectionResetError("Desconexão voluntária")

        return player_id

    # ── Handlers de eventos ──────────────────────────────────────

    def _on_join(self, conn: socket.socket, payload: dict) -> str | None:
        username = payload.get("username", "").strip()

        with self.lock:
            if self.state == State.IN_GAME:
                self._send(conn, make_error(ErrorCode.GAME_IN_PROGRESS, "Jogo em andamento. Aguarde a próxima partida."))
                return None

            if len(self.connections) >= MAX_PLAYERS:
                self._send(conn, make_error(ErrorCode.GAME_FULL, "Sala cheia (máx. 4 jogadores)."))
                return None

            if not username:
                self._send(conn, make_error(ErrorCode.INVALID_ACTION, "Username não pode ser vazio."))
                return None

            if self.game_state.username_taken(username):
                self._send(conn, make_error(ErrorCode.NAME_TAKEN, f"O nome '{username}' já está em uso."))
                return None

            player_id = str(uuid.uuid4())[:8]
            self.game_state.add_player(player_id, username)
            self.connections[player_id] = conn

            self._send(conn, make_welcome(player_id, self.state))

            players, ready_count = self.game_state.lobby_info()
            self._broadcast(make_lobby_update(players, ready_count))
            self._broadcast(make_player_event("joined", username, f"{username} entrou na sala."))

            print(f"[JOIN] {username} ({player_id})")
            return player_id

    def _on_ready(self, player_id: str):
        with self.lock:
            if self.state != State.WAITING_PLAYERS:
                return

            player = self.game_state.get_player(player_id)
            if not player:
                return
            player.ready = True

            players, ready_count = self.game_state.lobby_info()
            self._broadcast(make_lobby_update(players, ready_count))
            print(f"[READY] {player.username} está pronto. ({ready_count}/{len(players)})")

            if self.game_state.all_ready():
                self._start_countdown()

    def _on_action(self, player_id: str, command: str):
        with self.lock:
            if self.state != State.IN_GAME:
                conn = self.connections.get(player_id)
                if conn:
                    self._send(conn, make_error(ErrorCode.NOT_IN_GAME, "O jogo não está em andamento."))
                return

            player = self.game_state.get_player(player_id)
            if not player:
                return

            print(f"[ACTION] {player.username}: {command}")
            responses = self.game_state.process_action(player_id, command)

            conn = self.connections.get(player_id)
            for i, msg in enumerate(responses):
                if i == 0:
                    # Primeiro item: ACTION_RESULT → unicast
                    if conn:
                        self._send(conn, msg)
                else:
                    # Demais (ROOM_UPDATE etc.) → broadcast
                    self._broadcast(msg)

            # Verifica condição de vitória
            if responses and b'"__ESCAPED__"' in responses[0]:
                self._trigger_game_over("win")

    def _on_chat(self, player_id: str, message: str):
        with self.lock:
            player = self.game_state.get_player(player_id)
            if not player or not message.strip():
                return
            print(f"[CHAT] {player.username}: {message}")
            self._broadcast(make_chat_broadcast(player.username, message))

    def _on_disconnect(self, player_id: str | None, conn: socket.socket):
        if not player_id:
            try:
                conn.close()
            except OSError:
                pass
            return

        with self.lock:
            player = self.game_state.get_player(player_id)
            username = player.username if player else "?"
            self.game_state.remove_player(player_id)
            self.connections.pop(player_id, None)
            try:
                conn.close()
            except OSError:
                pass

            print(f"[DISC] {username} desconectou.")
            self._broadcast(make_player_event("left", username, f"{username} saiu da sala."))

            if self.state == State.WAITING_PLAYERS:
                players, ready_count = self.game_state.lobby_info()
                self._broadcast(make_lobby_update(players, ready_count))

            elif self.state == State.IN_GAME:
                if len(self.connections) < 1:
                    self._trigger_game_over("lose")

    # ── Countdown e início de jogo ───────────────────────────────

    def _start_countdown(self):
        """Chamado dentro do lock."""
        self.state = State.COUNTDOWN
        t = threading.Thread(target=self._countdown_loop, daemon=True)
        t.start()

    def _countdown_loop(self):
        for remaining in range(COUNTDOWN_SECONDS, 0, -1):
            self._broadcast(make_countdown(remaining))
            time.sleep(1)

        with self.lock:
            self.state = State.IN_GAME
            self._game_start_time = time.time()
            room = "laboratorio"
            desc = self.game_state.room_states[room]["description"]
            self._broadcast(make_game_start(room, desc, GAME_TIME_LIMIT))
            # Envia o estado inicial da sala para todos
            self._broadcast(self.game_state.initial_room_update(room))

        print("[GAME] Partida iniciada!")
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    # ── Timer do jogo ────────────────────────────────────────────

    def _timer_loop(self):
        while True:
            time.sleep(1)
            with self.lock:
                if self.state != State.IN_GAME:
                    break
                elapsed  = int(time.time() - self._game_start_time)
                remaining = GAME_TIME_LIMIT - elapsed

                if remaining <= 0:
                    self._trigger_game_over("lose")
                    break

                if remaining % TIMER_BROADCAST_INTERVAL == 0 or remaining in CRITICAL_TIME_MARKS:
                    self._broadcast(make_timer_update(remaining))
                    print(f"[TIMER] {remaining}s restantes.")

    # ── Game Over ────────────────────────────────────────────────

    def _trigger_game_over(self, result: str):
        """Chamado dentro do lock."""
        if self.state == State.GAME_OVER:
            return
        self.state = State.GAME_OVER
        elapsed = int(time.time() - self._game_start_time)

        if result == "win":
            msg = f"🏆 Vocês escaparam em {elapsed // 60}m {elapsed % 60}s! Parabéns!"
        else:
            msg = "💀 O tempo esgotou. Vocês não conseguiram escapar desta vez."

        self._broadcast(make_game_over(result, elapsed, msg))
        print(f"[GAME OVER] resultado={result} tempo={elapsed}s")

        # Aguarda 10 s e reseta para nova partida
        threading.Thread(target=self._schedule_reset, daemon=True).start()

    def _schedule_reset(self):
        time.sleep(10)
        with self.lock:
            self.game_state.reset()
            self.state = State.WAITING_PLAYERS
            players, ready_count = self.game_state.lobby_info()
            self._broadcast(make_lobby_update(players, ready_count))
            print("[RESET] Nova partida disponível.")

    # ── Envio de mensagens ───────────────────────────────────────

    def _send(self, conn: socket.socket, data: bytes):
        try:
            conn.sendall(data)
        except OSError:
            pass

    def _broadcast(self, data: bytes):
        for conn in list(self.connections.values()):
            self._send(conn, data)


# ── Entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ERP/1.0 Escape Room Server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    args = parser.parse_args()

    Server(args.host, args.port).start()
