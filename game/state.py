# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Gerenciamento de estado do jogo
# ─────────────────────────────────────────────────────────────────
import copy
from game.rooms import ROOMS, INITIAL_ROOM
from game.protocol import make_action_result, make_room_update, make_hint

DIRECTIONS = {"norte", "sul", "leste", "oeste"}


class Player:
    def __init__(self, player_id: str, username: str):
        self.player_id   = player_id
        self.username    = username
        self.ready       = False
        self.current_room = INITIAL_ROOM
        self.inventory: list[str] = []

    def to_dict(self) -> dict:
        return {"player_id": self.player_id, "username": self.username, "ready": self.ready}


class GameState:
    """
    Mantém o estado completo de uma partida:
      - Jogadores e seus inventários
      - Estado de cada sala (objetos visíveis, saídas desbloqueadas)
      - Índice de dicas por sala
    """

    def __init__(self):
        self.players: dict[str, Player] = {}       # player_id → Player
        self.room_states: dict = {}                # cópia mutável das salas
        self._hint_index: dict[str, int] = {}      # sala → próxima dica
        self._reset_rooms()

    # ── Setup ────────────────────────────────────────────────────

    def _reset_rooms(self):
        """Faz deep copy das salas para que o estado seja reiniciável."""
        self.room_states = copy.deepcopy(ROOMS)
        self._hint_index = {room: 0 for room in ROOMS}

    def reset(self):
        """Reseta o jogo para uma nova partida."""
        for player in self.players.values():
            player.current_room = INITIAL_ROOM
            player.inventory.clear()
            player.ready = False
        self._reset_rooms()

    # ── Jogadores ────────────────────────────────────────────────

    def add_player(self, player_id: str, username: str) -> Player:
        p = Player(player_id, username)
        self.players[player_id] = p
        return p

    def remove_player(self, player_id: str):
        self.players.pop(player_id, None)

    def get_player(self, player_id: str) -> Player | None:
        return self.players.get(player_id)

    def username_taken(self, username: str) -> bool:
        return any(p.username == username for p in self.players.values())

    def lobby_info(self) -> tuple[list[dict], int]:
        players = [p.to_dict() for p in self.players.values()]
        ready_count = sum(1 for p in self.players.values() if p.ready)
        return players, ready_count

    def all_ready(self) -> bool:
        if len(self.players) < 2:
            return False
        return all(p.ready for p in self.players.values())

    # ── Processamento de comandos ────────────────────────────────

    def process_action(self, player_id: str, command: str) -> list[bytes]:
        """
        Processa um comando ACTION de um jogador.
        Retorna lista de mensagens a enviar:
          - response[0] → ACTION_RESULT (unicast para quem enviou)
          - response[1] → ROOM_UPDATE (broadcast, opcional, se estado mudou)
        """
        player = self.players.get(player_id)
        if not player:
            return [make_action_result(False, "Jogador não encontrado.", False)]

        parts  = command.strip().lower().split()
        if not parts:
            return [make_action_result(False, "Comando vazio.", False)]

        verb = parts[0]

        if verb == "examinar" and len(parts) >= 2:
            return self._cmd_examinar(player, " ".join(parts[1:]))

        if verb == "pegar" and len(parts) >= 2:
            return self._cmd_pegar(player, " ".join(parts[1:]))

        if verb == "usar":
            # "usar <item>"  ou  "usar <item> em <obj>"
            rest = " ".join(parts[1:])
            if " em " in rest:
                halves = rest.split(" em ", 1)
                return self._cmd_usar(player, halves[0].strip(), halves[1].strip())
            return self._cmd_usar_simples(player, rest.strip())

        if verb == "ir" and len(parts) >= 2:
            return self._cmd_ir(player, parts[1])

        if verb == "inventario":
            return self._cmd_inventario(player)

        if verb == "dica":
            return self._cmd_dica(player)

        return [make_action_result(False, f"Comando desconhecido: '{command}'. Digite 'dica' se precisar de ajuda.", False)]

    # ── Comandos individuais ─────────────────────────────────────

    def _cmd_examinar(self, player: Player, obj_name: str) -> list[bytes]:
        room = self.room_states[player.current_room]
        obj  = self._find_object(room, obj_name)
        if not obj:
            return [make_action_result(False, f"Não há '{obj_name}' aqui para examinar.", False)]

        msg = obj["description"]

        # Revela objeto oculto
        if obj.get("reveals"):
            revealed_name = obj["reveals"]
            revealed = room["objects"].get(revealed_name)
            if revealed and revealed.get("hidden"):
                revealed["hidden"] = False
                if revealed.get("takeable"):
                    msg += f"\n[Você pode pegar: {revealed_name}]"

        return [make_action_result(True, msg, False)]

    def _cmd_pegar(self, player: Player, obj_name: str) -> list[bytes]:
        room = self.room_states[player.current_room]
        obj  = self._find_object(room, obj_name)
        if not obj:
            return [make_action_result(False, f"Não há '{obj_name}' aqui.", False)]
        if not obj.get("takeable"):
            return [make_action_result(False, f"Você não pode pegar '{obj_name}'.", False)]
        if obj_name in player.inventory:
            return [make_action_result(False, f"Você já tem '{obj_name}' no inventário.", False)]

        player.inventory.append(obj_name)
        # Remove da sala
        room["objects"].pop(obj_name, None)

        return [
            make_action_result(True, f"Você pegou: {obj_name}.", True),
            self._make_room_update(player.current_room),
        ]

    def _cmd_usar(self, player: Player, item_name: str, target_name: str) -> list[bytes]:
        """usar <item_do_inventário> em <objeto_da_sala>"""
        if item_name not in player.inventory:
            return [make_action_result(False, f"Você não tem '{item_name}' no inventário.", False)]

        room   = self.room_states[player.current_room]
        target = self._find_object(room, target_name)
        if not target:
            return [make_action_result(False, f"Não há '{target_name}' aqui.", False)]

        use_with = target.get("use_with")
        if not use_with or use_with["item"] != item_name:
            return [make_action_result(False, f"Você não pode usar '{item_name}' em '{target_name}'.", False)]

        # Sucesso: aplica efeito
        result_msg = use_with["result_msg"]
        state_changed = False

        if use_with.get("unlocks"):
            unlocked = use_with["unlocks"]
            # Destrava saída
            for direction, exit_data in room["exits"].items():
                if exit_data.get("locked") and (exit_data.get("key") == item_name or unlocked.startswith("saida")):
                    exit_data["locked"] = False
                    state_changed = True
            # Ou revela objeto
            if unlocked in room["objects"]:
                room["objects"][unlocked]["hidden"] = False
                room["objects"][unlocked]["takeable"] = True
                state_changed = True

        player.inventory.remove(item_name)

        responses = [make_action_result(True, result_msg, state_changed)]
        if state_changed:
            responses.append(self._make_room_update(player.current_room))
        return responses

    def _cmd_usar_simples(self, player: Player, item_name: str) -> list[bytes]:
        """usar <item> sem alvo — apenas descreve o item."""
        if item_name not in player.inventory:
            return [make_action_result(False, f"Você não tem '{item_name}' no inventário.", False)]
        room = self.room_states[player.current_room]
        # Tenta encontrar o objeto pelo nome no inventário (pode ter sido removido da sala)
        obj = None
        for r in self.room_states.values():
            obj = r["objects"].get(item_name)
            if obj:
                break
        desc = obj["description"] if obj else f"Você está segurando: {item_name}."
        return [make_action_result(True, f"Use 'usar {item_name} em <objeto>' para combiná-lo com algo. {desc}", False)]

    def _cmd_ir(self, player: Player, direction: str) -> list[bytes]:
        if direction not in DIRECTIONS:
            return [make_action_result(False, f"Direção inválida: '{direction}'. Use norte, sul, leste ou oeste.", False)]

        room  = self.room_states[player.current_room]
        exits = room.get("exits", {})
        if direction not in exits:
            return [make_action_result(False, f"Não há saída ao {direction} daqui.", False)]

        exit_data = exits[direction]
        if exit_data.get("locked"):
            return [make_action_result(False, exit_data.get("locked_msg", "Saída bloqueada."), False)]

        destination = exit_data["room"]

        # ── Condição de vitória ──────────────────────────────────
        if destination == "__ESCAPE__":
            return [make_action_result(True, "__ESCAPED__", True)]  # sinal especial para o servidor

        player.current_room = destination
        new_room = self.room_states[destination]

        return [
            make_action_result(True, f"Você foi para {destination}.\n{new_room['description']}", True),
            self._make_room_update(destination),
        ]

    def _cmd_inventario(self, player: Player) -> list[bytes]:
        if not player.inventory:
            msg = "Seu inventário está vazio."
        else:
            msg = "Inventário: " + ", ".join(player.inventory)
        return [make_action_result(True, msg, False)]

    def _cmd_dica(self, player: Player) -> list[bytes]:
        room_key = player.current_room
        hints    = ROOMS[room_key]["hints"]
        idx      = self._hint_index.get(room_key, 0)
        if idx >= len(hints):
            hint_text = "Não há mais dicas para esta sala. Você já tem tudo que precisa!"
        else:
            hint_text = hints[idx]
            self._hint_index[room_key] = idx + 1
        return [make_hint(hint_text)]

    # ── Helpers ──────────────────────────────────────────────────

    def _find_object(self, room: dict, name: str) -> dict | None:
        """Busca objeto pelo nome, ignorando objetos hidden."""
        obj = room["objects"].get(name)
        if obj and not obj.get("hidden", False):
            return obj
        return None

    def _make_room_update(self, room_key: str) -> bytes:
        room = self.room_states[room_key]
        visible_objects = [
            name for name, obj in room["objects"].items()
            if not obj.get("hidden", False)
        ]
        players_here = [
            p.username for p in self.players.values()
            if p.current_room == room_key
        ]
        exits_info = {
            direction: {"locked": data.get("locked", False), "room": data["room"]}
            for direction, data in room.get("exits", {}).items()
        }
        return make_room_update(
            room_state={"name": room_key, "exits": exits_info},
            objects=visible_objects,
            players_here=players_here,
        )

    def initial_room_update(self, room_key: str) -> bytes:
        return self._make_room_update(room_key)
