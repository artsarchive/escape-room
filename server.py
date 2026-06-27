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
    make_map_vote_state, make_map_selected,
    ErrorCode, COUNTDOWN_SECONDS, GAME_TIME_LIMIT,
    TIMER_BROADCAST_INTERVAL, CRITICAL_TIME_MARKS,
    MIN_PLAYERS, MAX_PLAYERS,
)
from game.state import GameState
from game.rooms import MAPS

HOST = "0.0.0.0"
PORT = 5000


class Server:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.state      = State.WAITING_PLAYERS
        self.game_state = GameState()
        self.lock       = threading.Lock()

        # player_id → socket
        self.connections: dict[str, socket.socket] = {}

        # Votos de mapa: player_id → map_key
        self._map_votes: dict[str, str] = {}

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

        valid_types = {
            ClientMsg.JOIN,
            ClientMsg.READY,
            ClientMsg.MAP_VOTE,
            ClientMsg.ACTION,
            ClientMsg.CHAT,
            ClientMsg.DISCONNECT,
        }

        if msg_type not in valid_types:
            self._send(conn, make_error(
                ErrorCode.INVALID_ACTION,
                f"Tipo de mensagem desconhecido: {msg_type}"
            ))
            return player_id

        if msg_type == ClientMsg.JOIN:
            return self._on_join(conn, payload)

        if player_id is None:
            self._send(conn, make_error(ErrorCode.INVALID_ACTION, "Envie JOIN antes de qualquer outro comando."))
            return None

        if msg_type == ClientMsg.READY:
            self._on_ready(player_id)

        elif msg_type == ClientMsg.MAP_VOTE:
            self._on_map_vote(player_id, payload.get("map", ""))

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
            if self.state != State.WAITING_PLAYERS:
                self._send(conn, make_error(
                    ErrorCode.GAME_IN_PROGRESS,
                    "A partida já foi iniciada ou está em contagem regressiva. Aguarde a próxima partida."
                ))
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
            # Informa o estado atual de votos para o novo jogador
            self._send(conn, self._make_map_vote_state())

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

    def _on_map_vote(self, player_id: str, map_key: str):
        with self.lock:
            if self.state != State.WAITING_PLAYERS:
                return
            if map_key not in MAPS:
                conn = self.connections.get(player_id)
                if conn:
                    self._send(conn, make_error(ErrorCode.INVALID_ACTION, f"Mapa inválido: '{map_key}'. Opções: {list(MAPS.keys())}"))
                return

            player = self.game_state.get_player(player_id)
            if not player:
                return

            self._map_votes[player_id] = map_key
            print(f"[VOTE] {player.username} votou em '{map_key}'")
            self._broadcast(self._make_map_vote_state())

    def _make_map_vote_state(self) -> bytes:
        votes: dict[str, int] = {k: 0 for k in MAPS}
        for map_key in self._map_votes.values():
            if map_key in votes:
                votes[map_key] += 1
        maps_info = {k: v["name"] for k, v in MAPS.items()}
        return make_map_vote_state(votes, maps_info)

    def _resolve_map(self) -> str:
        """Retorna o mapa com mais votos. Em empate, escolhe o primeiro."""
        tally: dict[str, int] = {k: 0 for k in MAPS}
        for map_key in self._map_votes.values():
            if map_key in tally:
                tally[map_key] += 1
        return max(tally, key=lambda k: tally[k])

    def _on_action(self, player_id: str, command: str):
        if self.state != State.IN_GAME:
            return
        
        responses = self.game_state.process_action(player_id, command)
        conn = self.connections.get(player_id)
        
        if conn:
            for res in responses:
                # CORREÇÃO: Se for uma atualização de sala ou evento, transmite para todos!
                # O próprio cliente já filtra e ignora se não for a sala dele.
                msg_str = res.decode("utf-8", errors="ignore")
                if msg_str.startswith("ROOM_UPDATE") or msg_str.startswith("PLAYER_EVENT"):
                    self._broadcast(res)
                else:
                    self._send(conn, res)

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

            elif self.state == State.COUNTDOWN:
                if len(self.connections) < MIN_PLAYERS or not self.game_state.all_ready():
                    self._cancel_countdown_locked(
                        "A contagem foi cancelada porque não há jogadores suficientes para iniciar."
                    )

            elif self.state == State.IN_GAME:
                if len(self.connections) < MIN_PLAYERS:
                    self._trigger_game_over(
                        "lose",
                        "💀 A partida foi encerrada porque restaram menos de 2 jogadores conectados."
                    )

    # ── Countdown e início de jogo ───────────────────────────────

    def _cancel_countdown_locked(self, reason: str):
        """
        Cancela a contagem regressiva e volta para o lobby.
        Deve ser chamado com self.lock já adquirido.
        """
        if self.state != State.COUNTDOWN:
            return

        self.state = State.WAITING_PLAYERS
        players, ready_count = self.game_state.lobby_info()
        self._broadcast(make_lobby_update(players, ready_count))
        self._broadcast(make_player_event("countdown_cancelled", "Servidor", reason))
        print(f"[COUNTDOWN] Cancelado: {reason}")

    def _start_countdown(self):
        """Chamado dentro do lock."""
        self.state = State.COUNTDOWN
        t = threading.Thread(target=self._countdown_loop, daemon=True)
        t.start()

    def _countdown_loop(self):
        for remaining in range(COUNTDOWN_SECONDS, 0, -1):
            with self.lock:
                if self.state != State.COUNTDOWN:
                    return

                if len(self.connections) < MIN_PLAYERS or not self.game_state.all_ready():
                    self._cancel_countdown_locked(
                        "A contagem foi cancelada porque não há jogadores suficientes para iniciar."
                    )
                    return

                self._broadcast(make_countdown(remaining))

            time.sleep(1)

        with self.lock:
            if self.state != State.COUNTDOWN:
                return

            if len(self.connections) < MIN_PLAYERS or not self.game_state.all_ready():
                self._cancel_countdown_locked(
                    "A contagem foi cancelada porque não há jogadores suficientes para iniciar."
                )
                return

            # Resolve mapa vencedor e aplica
            chosen_map = self._resolve_map()
            self.game_state.set_map(chosen_map)
            map_name = MAPS[chosen_map]["name"]
            self._broadcast(make_map_selected(chosen_map, map_name))
            print(f"[MAP] Mapa selecionado: {chosen_map} ({map_name})")

            self.state = State.IN_GAME
            self._game_start_time = time.time()

            # --- CORREÇÃO: Unicast do GAME_START para salas assimétricas ---
            for pid, pconn in self.connections.items():
                p = self.game_state.get_player(pid)
                if p:
                    player_room = p.current_room
                    desc = self.game_state.room_states[player_room]["description"]
                    # Envia a mensagem de início personalizada para a sala do jogador
                    self._send(pconn, make_game_start(player_room, desc, GAME_TIME_LIMIT))
                    # Envia o estado inicial dos objetos específicos daquela sala
                    self._send(pconn, self.game_state.initial_room_update(player_room, p))

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

    def _trigger_game_over(self, result: str, message: str | None = None):
        """Chamado dentro do lock."""
        if self.state == State.GAME_OVER:
            return
        self.state = State.GAME_OVER
        elapsed = int(time.time() - self._game_start_time)

        if result == "win":
            msg = message or f"🏆 Vocês escaparam em {elapsed // 60}m {elapsed % 60}s! Parabéns!"
        else:
            msg = message or "💀 O tempo esgotou. Vocês não conseguiram escapar desta vez."

        self._broadcast(make_game_over(result, elapsed, msg))
        print(f"[GAME OVER] resultado={result} tempo={elapsed}s")

        # Aguarda 10 s e reseta para nova partida
        threading.Thread(target=self._schedule_reset, daemon=True).start()

    def _schedule_reset(self):
        time.sleep(10)
        with self.lock:
            self.game_state.reset()
            self._map_votes.clear()
            self.state = State.WAITING_PLAYERS
            players, ready_count = self.game_state.lobby_info()
            self._broadcast(make_lobby_update(players, ready_count))
            self._broadcast(self._make_map_vote_state())
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