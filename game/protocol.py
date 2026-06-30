# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Escape Room Protocol
#  Constantes, serialização e builders de mensagem
# ─────────────────────────────────────────────────────────────────
import json

ENCODING = "utf-8"
DELIMITER = b"\n"
BUFFER_SIZE = 4096

# ── Limites da sessão ────────────────────────────────────────────
MIN_PLAYERS = 2
MAX_PLAYERS = 4
COUNTDOWN_SECONDS = 10
GAME_TIME_LIMIT = 1800        # 30 minutos em segundos
TIMER_BROADCAST_INTERVAL = 120 # broadcast a cada 2 minutos
CRITICAL_TIME_MARKS = {300, 60, 30, 10}  # alertas extras nesses segundos

# ── Estados do servidor ──────────────────────────────────────────
class State:
    WAITING_PLAYERS = "WAITING_PLAYERS"
    COUNTDOWN       = "COUNTDOWN"
    IN_GAME         = "IN_GAME"
    GAME_OVER       = "GAME_OVER"

# ── Tipos de mensagem: Cliente → Servidor ────────────────────────
class ClientMsg:
    JOIN       = "JOIN"
    READY      = "READY"
    MAP_VOTE   = "MAP_VOTE"    # payload: {"map": "hospital"}
    ACTION     = "ACTION"
    CHAT       = "CHAT"
    DISCONNECT = "DISCONNECT"

# ── Tipos de mensagem: Servidor → Cliente ────────────────────────
class ServerMsg:
    WELCOME        = "WELCOME"
    LOBBY_UPDATE   = "LOBBY_UPDATE"
    MAP_VOTE_STATE = "MAP_VOTE_STATE"  # payload: {"votes": {"hospital": 1, "museu": 0}, "maps": {...}}
    MAP_SELECTED   = "MAP_SELECTED"    # payload: {"map": str, "map_name": str}
    COUNTDOWN      = "COUNTDOWN"
    GAME_START     = "GAME_START"
    ACTION_RESULT  = "ACTION_RESULT"
    ROOM_UPDATE    = "ROOM_UPDATE"
    CHAT_BROADCAST = "CHAT_BROADCAST"
    TIMER_UPDATE   = "TIMER_UPDATE"
    PLAYER_EVENT   = "PLAYER_EVENT"
    HINT           = "HINT"
    GAME_OVER      = "GAME_OVER"
    ERROR          = "ERROR"

# ── Códigos de erro ──────────────────────────────────────────────
class ErrorCode:
    NAME_TAKEN        = "NAME_TAKEN"
    GAME_FULL         = "GAME_FULL"
    GAME_IN_PROGRESS  = "GAME_IN_PROGRESS"
    INVALID_ACTION    = "INVALID_ACTION"
    NOT_IN_GAME       = "NOT_IN_GAME"

# ─────────────────────────────────────────────────────────────────
#  Serialização / Desserialização
# ─────────────────────────────────────────────────────────────────

def encode(msg_type: str, payload: dict) -> bytes:
    """Serializa uma mensagem ERP para bytes prontos para envio."""
    message = json.dumps({"type": msg_type, "payload": payload}, ensure_ascii=False)
    return (message + "\n").encode(ENCODING)

def decode(raw: str) -> tuple[str, dict]:
    """
    Desserializa uma linha recebida do socket.
    Retorna (type, payload) ou lança ValueError se inválida.
    """
    data = json.loads(raw.strip())
    if "type" not in data or "payload" not in data:
        raise ValueError("Mensagem sem campos obrigatórios: 'type' e 'payload'")
    return data["type"], data["payload"]

# ─────────────────────────────────────────────────────────────────
#  Builders — Servidor → Cliente
# ─────────────────────────────────────────────────────────────────

def make_map_vote_state(votes: dict, maps: dict) -> bytes:
    """votes: {"hospital": N}  maps: {"hospital": "🏥 Hospital Abandonado", ...}"""
    return encode(ServerMsg.MAP_VOTE_STATE, {"votes": votes, "maps": maps})

def make_map_selected(map_key: str, map_name: str) -> bytes:
    return encode(ServerMsg.MAP_SELECTED, {"map": map_key, "map_name": map_name})

def make_welcome(player_id: str, server_state: str) -> bytes:
    return encode(ServerMsg.WELCOME, {
        "player_id": player_id,
        "server_state": server_state,
    })

def make_lobby_update(players: list[dict], ready_count: int) -> bytes:
    return encode(ServerMsg.LOBBY_UPDATE, {
        "players": players,          # [{"username": str, "ready": bool}, ...]
        "ready_count": ready_count,
        "total": len(players),
    })

def make_countdown(seconds: int) -> bytes:
    return encode(ServerMsg.COUNTDOWN, {"seconds": seconds})

def make_game_start(room_name: str, description: str, time_limit: int) -> bytes:
    return encode(ServerMsg.GAME_START, {
        "room": room_name,
        "description": description,
        "time_limit": time_limit,
    })

def make_action_result(success: bool, message: str, state_changed: bool = False) -> bytes:
    return encode(ServerMsg.ACTION_RESULT, {
        "success": success,
        "message": message,
        "state_changed": state_changed,
    })

def make_room_update(room_state: dict, objects: list[str], players_here: list[str]) -> bytes:
    return encode(ServerMsg.ROOM_UPDATE, {
        "room_state": room_state,
        "objects": objects,
        "players_here": players_here,
    })

def make_chat_broadcast(sender: str, message: str) -> bytes:
    return encode(ServerMsg.CHAT_BROADCAST, {
        "from": sender,
        "message": message,
    })

def make_timer_update(remaining: int) -> bytes:
    return encode(ServerMsg.TIMER_UPDATE, {"remaining": remaining})

def make_player_event(event: str, player: str, detail: str = "") -> bytes:
    """event: 'joined' | 'left' | 'moved' | 'solved' | 'match_reset' | 'countdown_cancelled'"""
    return encode(ServerMsg.PLAYER_EVENT, {
        "event": event,
        "player": player,
        "detail": detail,
    })

def make_hint(text: str) -> bytes:
    return encode(ServerMsg.HINT, {"text": text})

def make_game_over(result: str, time_elapsed: int, message: str) -> bytes:
    """result: 'win' | 'lose'"""
    return encode(ServerMsg.GAME_OVER, {
        "result": result,
        "time_elapsed": time_elapsed,
        "message": message,
    })

def make_error(code: str, message: str) -> bytes:
    return encode(ServerMsg.ERROR, {
        "code": code,
        "message": message,
    })

# ─────────────────────────────────────────────────────────────────
#  Builders — Cliente → Servidor  (usados no client.py)
# ─────────────────────────────────────────────────────────────────

def make_map_vote(map_key: str) -> bytes:
    return encode(ClientMsg.MAP_VOTE, {"map": map_key})

def make_join(username: str) -> bytes:
    return encode(ClientMsg.JOIN, {"username": username})

def make_ready() -> bytes:
    return encode(ClientMsg.READY, {})

def make_action(command: str) -> bytes:
    return encode(ClientMsg.ACTION, {"command": command})

def make_chat(message: str) -> bytes:
    return encode(ClientMsg.CHAT, {"message": message})

def make_disconnect() -> bytes:
    return encode(ClientMsg.DISCONNECT, {})