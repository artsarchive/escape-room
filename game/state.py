# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Gerenciamento de estado do jogo (Co-op Integrado)
# ─────────────────────────────────────────────────────────────────
import copy
import re
import unicodedata

from game.rooms import MAPS, ROOMS, INITIAL_ROOM
from game.protocol import make_action_result, make_room_update, make_hint, make_player_event

DIRECTIONS = {"norte", "sul", "leste", "oeste"}

OBJECT_ALIASES = {
    "porta norte": "porta_norte",
    "porta leste": "porta_leste",
    "porta sul": "porta_sul",
    "painel": "painel_de_controle",
    "terminal": "terminal_de_monitoramento",
    "cofre": "cofre_medico",
    "caixa": "caixa_de_ferramentas",
    "servidor": "servidor_de_ti",
    # Dicionário de senhas da campanha:
    "8520": "senha_terminal",
    "440": "energia_ativada",
    "440v": "energia_ativada",
    "1968": "ano_fundacao",
    "314": "codigo_valvula",
    "7701": "id_medico",
    "9999": "codigo_cofre",
    "1234": "senha_ferramentas"
}

class Player:
    def __init__(self, player_id: str, username: str, role: int = 0):
        self.player_id    = player_id
        self.username     = username
        self.role         = role
        self.ready        = False
        self.current_room = ""
        self.inventory: list[str] = []

    def to_dict(self) -> dict:
        return {"player_id": self.player_id, "username": self.username, "ready": self.ready}


class GameState:
    def __init__(self):
        self.players: dict[str, Player] = {}
        self.room_states: dict = {}
        self._hint_index: dict[str, int] = {}
        self._active_map_key: str = "hospital"
        self._reset_rooms()

    def _active_map(self) -> dict:
        return MAPS[self._active_map_key]

    def _active_rooms(self) -> dict:
        return self._active_map()["rooms"]

    def _reset_rooms(self):
        rooms = self._active_rooms()
        self.room_states = copy.deepcopy(rooms)
        self._hint_index = {room: 0 for room in rooms}

    def initial_room_for_player(self, player: Player) -> str:
        mapa_ativo = self._active_map()
        if "initial_rooms" in mapa_ativo:
            role_efetivo = self._effective_role(player)
            return mapa_ativo["initial_rooms"].get(role_efetivo, mapa_ativo["initial_rooms"].get(0))
        return mapa_ativo.get("initial_room", "")

    def set_map(self, map_key: str):
        if map_key in MAPS:
            self._active_map_key = map_key
            self._reset_rooms()
            # Se algum dia houver mapas com quantidade diferente de papéis,
            # os roles precisam ser recalculados antes de reposicionar jogadores.
            self.redistribute_roles()
            for player in self.players.values():
                player.current_room = self.initial_room_for_player(player)

    def required_roles(self) -> list[int]:
        """Retorna os papéis/caminhos essenciais do mapa ativo."""
        initial_rooms = self._active_map().get("initial_rooms")
        if not initial_rooms:
            return [0]
        return sorted(initial_rooms.keys())

    def redistribute_roles(self):
        """Redistribui os papéis entre os jogadores conectados.

        Exemplo em mapa com roles [0, 1]:
          2 jogadores -> 0, 1
          3 jogadores -> 0, 1, 0
          4 jogadores -> 0, 1, 0, 1
        """
        roles = self.required_roles()
        for idx, player in enumerate(self.players.values()):
            player.role = roles[idx % len(roles)]

    def has_required_roles_connected(self) -> bool:
        """Verifica se todos os papéis essenciais ainda têm ao menos um jogador."""
        required = set(self.required_roles())
        active = {self._effective_role(player) for player in self.players.values()}
        return required.issubset(active)

    def reset(self, redistribute_roles: bool = False):
        self._reset_rooms()
        if redistribute_roles:
            self.redistribute_roles()
        for player in self.players.values():
            player.inventory.clear()
            player.ready = False
            player.current_room = self.initial_room_for_player(player)

    def add_player(self, player_id: str, username: str) -> Player:
        roles = self.required_roles()
        role = roles[len(self.players) % len(roles)]
        p = Player(player_id, username, role)
        p.current_room = self.initial_room_for_player(p)
        self.players[player_id] = p
        return p

    def remove_player(self, player_id: str):
        self.players.pop(player_id, None)

    def drop_items_in_room(self, room_key: str, item_keys: list[str]) -> list[str]:
        """Devolve ao mapa os itens que estavam no inventário de um jogador.

        Usado quando um jogador desconecta durante IN_GAME, mas a partida
        continua. Os itens ficam "no chão" da sala onde ele caiu, para que
        outro jogador do mesmo caminho possa pegá-los sem refazer puzzles.
        """
        if not room_key or room_key not in self.room_states:
            return []

        room = self.room_states[room_key]
        dropped: list[str] = []

        for item_key in item_keys:
            if not item_key:
                continue

            if item_key in room["objects"]:
                obj = room["objects"][item_key]
            else:
                obj = self._original_object_definition(item_key)
                room["objects"][item_key] = obj

            obj["hidden"] = False
            obj["takeable"] = True
            dropped.append(item_key)

        return dropped

    def _original_object_definition(self, item_key: str) -> dict:
        for room in self._active_rooms().values():
            obj = room.get("objects", {}).get(item_key)
            if obj is not None:
                return copy.deepcopy(obj)

        return {
            "description": f"Item deixado por um jogador desconectado: {item_key}.",
            "takeable": True,
            "hidden": False,
        }

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
        if not self.has_required_roles_connected():
            return False
        return all(p.ready for p in self.players.values())

    def process_action(self, player_id: str, command: str) -> list[bytes]:
        player = self.players.get(player_id)
        if not player: return []

        command = self._normalize_spaces(command)
        if not command: return []
        parts = command.split()
        verb = self._normalize_text(parts[0])

        if verb in {"olhar", "sala"}:
            room_desc = self.room_states[player.current_room]["description"]
            return [make_action_result(True, f"Você olha ao redor...\n{room_desc}", False), self._make_room_update(player.current_room, player)]
        if verb == "examinar" and len(parts) >= 2: return self._cmd_examinar(player, " ".join(parts[1:]))
        if verb == "pegar" and len(parts) >= 2: return self._cmd_pegar(player, " ".join(parts[1:]))
        
        if verb == "usar":
            rest = command[len(parts[0]):].strip()
            halves = re.split(r"\s+em\s+", rest, maxsplit=1, flags=re.IGNORECASE)
            if len(halves) == 2: return self._cmd_usar(player, halves[0].strip(), halves[1].strip())
            return self._cmd_usar_simples(player, rest.strip())
            
        if verb in {"colocar", "digitar", "inserir"}:
            rest = command[len(parts[0]):].strip()
            halves = re.split(r"\s+(?:no|na|em)\s+", rest, maxsplit=1, flags=re.IGNORECASE)
            if len(halves) == 2: return self._cmd_colocar(player, halves[0].strip(), halves[1].strip())
            return [make_action_result(False, "Use o formato: colocar <senha> no <objeto>.", False)]
            
        if verb == "ir" and len(parts) >= 2: return self._cmd_ir(player, parts[1])
        if verb in {"inventario", "inventário"}: return self._cmd_inventario(player)
        if verb == "dica": return self._cmd_dica(player)

        return [make_action_result(False, f"Comando desconhecido.", False)]

    def _cmd_examinar(self, player: Player, obj_name: str) -> list[bytes]:
        room_key = player.current_room
        room = self.room_states[room_key]
        obj_key, obj = self._find_object(room, obj_name, player)
        if not obj: return [make_action_result(False, f"Não há '{obj_name}' aqui.", False)]

        msg = obj["description"]
        state_changed = False

        if obj.get("reveals"):
            revealed_name = obj["reveals"]
            revealed = room["objects"].get(revealed_name)
            if revealed and revealed.get("hidden"):
                revealed["hidden"] = False
                state_changed = True
                if revealed.get("takeable") and self._can_see_object(revealed, player):
                    msg += f"\n[Você achou: {revealed_name}]"

        responses = [make_action_result(True, msg, state_changed)]
        if state_changed: responses.append(self._make_room_update(room_key, player))
        return responses

    def _cmd_pegar(self, player: Player, obj_name: str) -> list[bytes]:
        room = self.room_states[player.current_room]
        obj_key, obj = self._find_object(room, obj_name, player)
        if not obj: return [make_action_result(False, f"Não há '{obj_name}' aqui.", False)]
        if not obj.get("takeable"): return [make_action_result(False, f"Você não pode pegar isso.", False)]
        if obj_key in player.inventory: return [make_action_result(False, f"Já está no inventário.", False)]

        player.inventory.append(obj_key)
        room["objects"].pop(obj_key, None)
        return [make_action_result(True, f"Você pegou: {obj_key}.", True), self._make_room_update(player.current_room, player)]

    def _cmd_usar(self, player: Player, item_name: str, target_name: str) -> list[bytes]:
        item_key = self._resolve_inventory_item(player, item_name)
        if not item_key: return [make_action_result(False, f"Você não tem '{item_name}'.", False)]

        target_name = self._resolve_contextual_target(player, target_name)
        room = self.room_states[player.current_room]
        target_key, target = self._find_object(room, target_name, player)
        if not target: return [make_action_result(False, f"Não há '{target_name}' aqui.", False)]

        use_with = target.get("use_with")
        if not use_with or use_with["item"] != item_key:
            return [make_action_result(False, f"Isso não funciona no '{target_key}'.", False)]

        result_msg = use_with["result_msg"]
        state_changed = False

        if use_with.get("unlocks"):
            unlocked = use_with["unlocks"]
            
            # Porta Final (Dupla Checagem)
            if unlocked == "saida_norte" and player.current_room == "corredor_central":
                target["resolvido"] = True
                disp_esq = room["objects"].get("dispositivo_esquerdo", {})
                disp_dir = room["objects"].get("dispositivo_direito", {})
                if disp_esq.get("resolvido", False) and disp_dir.get("resolvido", False):
                    if "norte" in room.get("exits", {}): room["exits"]["norte"]["locked"] = False
                    state_changed = True
                    result_msg += "\n[Ambas as chaves ativadas! A porta cedeu!]"
                else:
                    state_changed = True
                    result_msg += "\n[Aguardando o parceiro girar a outra chave...]"
            else:
                for direction, exit_data in room["exits"].items():
                    if exit_data.get("locked") and (exit_data.get("key") == item_key or unlocked.startswith("saida")):
                        exit_data["locked"] = False
                        state_changed = True

        player.inventory.remove(item_key)
        responses = [make_action_result(True, result_msg, state_changed)]
        if state_changed: responses.append(self._make_room_update(player.current_room, player))
        return responses

    def _cmd_colocar(self, player: Player, valor: str, target_name: str) -> list[bytes]:
        target_name = self._resolve_contextual_target(player, target_name)
        room = self.room_states[player.current_room]
        target_key, target = self._find_object(room, target_name, player)
        if not target: return [make_action_result(False, f"Não há '{target_name}' aqui.", False)]

        valor_norm = self._normalize_text(valor)

        # ── EVENTOS COOPERATIVOS REMOTOS ──
        
        # 1. P2 Liga Energia -> Liga tela do P1
        if target_key == "painel_de_controle" and valor_norm in ["440", "440v"]:
            result_msg = "SISTEMA OPERACIONAL. Um estrondo ecoa pelos andares. A energia foi reestabelecida!"
            responses = [make_action_result(True, result_msg, True)]
            if "recepcao" in self.room_states:
                sala_p1 = self.room_states["recepcao"]
                if "terminal_de_monitoramento" in sala_p1["objects"]:
                    sala_p1["objects"]["terminal_de_monitoramento"]["description"] = "O monitor ligou! Log piscando em vermelho: 'ACESSO CONSULTÓRIO = 8520'."
                responses.append(self._make_room_update("recepcao", None))
            responses.append(self._make_room_update(player.current_room, player))
            responses.append(make_player_event("solved", player.username, f"⚡ {player.username} religou a energia do hospital!"))
            return responses

        # 2. P2 Libera Servidor -> Abre porta do P1
        if target_key == "servidor_de_ti" and valor_norm == "7701":
            result_msg = "ID ACEITO. O servidor destravou remotamente as fechaduras da Ala Médica."
            responses = [make_action_result(True, result_msg, True)]
            if "consultorio" in self.room_states:
                sala_p1 = self.room_states["consultorio"]
                if "norte" in sala_p1.get("exits", {}):
                    sala_p1["exits"]["norte"]["locked"] = False
                    sala_p1["exits"]["norte"]["locked_msg"] = ""
                if "porta_norte" in sala_p1["objects"]:
                    sala_p1["objects"]["porta_norte"]["description"] = "A luz do leitor mudou para VERDE. Destrancada pelo TI."
                responses.append(self._make_room_update("consultorio", None))
            responses.append(self._make_room_update(player.current_room, player))
            responses.append(make_player_event("solved", player.username, f"💻 {player.username} invadiu o sistema e liberou as portas superiores!"))
            return responses

        use_with = target.get("use_with")
        if not use_with: return [make_action_result(False, f"Você não pode inserir códigos no '{target_key}'.", False)]

        expected_item = use_with["item"]
        if valor_norm != self._normalize_text(expected_item) and self._alias_for(valor) != expected_item:
            return [make_action_result(False, "Código incorreto.", False)]

        result_msg = use_with["result_msg"]
        state_changed = False

        if use_with.get("unlocks"):
            unlocked = use_with["unlocks"]
            for direction, exit_data in room["exits"].items():
                if exit_data.get("locked") and (exit_data.get("key") == expected_item or unlocked.startswith("saida")):
                    exit_data["locked"] = False
                    state_changed = True
            if unlocked in room["objects"]:
                room["objects"][unlocked]["hidden"] = False
                room["objects"][unlocked]["takeable"] = True
                state_changed = True

        responses = [make_action_result(True, result_msg, state_changed)]
        if state_changed: responses.append(self._make_room_update(player.current_room, player))
        return responses

    def _cmd_usar_simples(self, player: Player, item_name: str) -> list[bytes]:
        item_key = self._resolve_inventory_item(player, item_name)
        if not item_key: return [make_action_result(False, f"Você não tem '{item_name}'.", False)]
        return [make_action_result(True, f"Use 'usar {item_key} em <objeto>'.", False)]

    def _cmd_ir(self, player: Player, direction: str) -> list[bytes]:
        direction = self._normalize_text(direction)
        if direction not in DIRECTIONS: return [make_action_result(False, f"Use norte, sul, leste ou oeste.", False)]

        old_room_key = player.current_room
        room  = self.room_states[old_room_key]
        exits = room.get("exits", {})
        
        if direction not in exits: return [make_action_result(False, f"Não há saída para lá.", False)]
        exit_data = exits[direction]
        if exit_data.get("locked"): return [make_action_result(False, exit_data.get("locked_msg", "Bloqueada."), False)]

        destination = exit_data["room"]
        if destination == "__ESCAPE__": return [make_action_result(True, "__ESCAPED__", True)]

        player.current_room = destination
        new_room = self.room_states[destination]

        responses = [
            make_action_result(True, f"Você foi para {destination}.\n{new_room['description']}", True),
            self._make_room_update(old_room_key, player),
            self._make_room_update(destination, player)
        ]

        # EVENTO: Celebração blindada contra falsos positivos. 
        # Verifica rigorosamente se existe ALGUÉM além dele FÍSICAMENTE alocado na nova sala.
        if destination == "corredor_central":
            outros_aqui = [p for p in self.players.values() if p.current_room == "corredor_central" and p.player_id != player.player_id]
            if outros_aqui:
                responses.append(make_player_event("moved", player.username, f"🎉 {player.username} chegou ao corredor. A equipe finalmente se reencontrou!"))

        return responses

    def _cmd_inventario(self, player: Player) -> list[bytes]:
        msg = "Inventário: " + ", ".join(player.inventory) if player.inventory else "Inventário vazio."
        return [make_action_result(True, msg, False)]

    def _cmd_dica(self, player: Player) -> list[bytes]:
        room_key = player.current_room
        hints = self._active_rooms()[room_key]["hints"]
        idx = self._hint_index.get(room_key, 0)
        if idx >= len(hints): return [make_hint("Sem mais dicas.")]
        self._hint_index[room_key] = idx + 1
        return [make_hint(hints[idx])]

    def _effective_role(self, player: Player) -> int:
        roles = self.required_roles()
        return roles[player.role % len(roles)]

    def _can_see_object(self, obj: dict, player: Player) -> bool:
        role = obj.get("assigned_to_role")
        if role is None: return True
        return self._effective_role(player) == role

    def _resolve_contextual_target(self, player: Player, target_name: str) -> str:
        """Resolve alvos genéricos dependentes da sala.

        Exemplo: se o jogador digitar "colocar 8520 na porta" na recepção,
        o jogo entende que a "porta" é a porta_leste, porque é a única
        porta interativa visível naquela sala.
        """
        if self._normalize_text(target_name) != "porta":
            return target_name

        room = self.room_states[player.current_room]

        def visible_porta_candidates(require_use_with: bool) -> list[str]:
            candidates = []
            for key, obj in room["objects"].items():
                if obj.get("hidden", False):
                    continue
                if not key.startswith("porta"):
                    continue
                if not self._can_see_object(obj, player):
                    continue
                if require_use_with and not obj.get("use_with"):
                    continue
                candidates.append(key)
            return candidates

        # Para comandos do tipo "colocar senha na porta", prioriza portas com use_with.
        candidates = visible_porta_candidates(require_use_with=True)
        if len(candidates) == 1:
            return candidates[0]

        # Fallback: se só existir uma porta visível na sala, usa ela.
        candidates = visible_porta_candidates(require_use_with=False)
        if len(candidates) == 1:
            return candidates[0]

        return target_name

    def _normalize_text(self, text: str) -> str:
        text = str(text).strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", text.replace("_", " ").replace("-", " ")).strip()

    def _normalize_spaces(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text).strip())

    def _alias_for(self, name: str) -> str | None:
        norm = self._normalize_text(name)
        for alias, target in OBJECT_ALIASES.items():
            if self._normalize_text(alias) == norm: return target
        return None

    def _resolve_object_key(self, room: dict, name: str, include_hidden: bool = False, player: Player = None) -> str | None:
        norm = self._normalize_text(name)
        for key, obj in room["objects"].items():
            if self._normalize_text(key) == norm:
                if obj.get("hidden", False) and not include_hidden: return None
                if player and not self._can_see_object(obj, player): return None
                return key
        alias_tgt = self._alias_for(name)
        if alias_tgt and alias_tgt in room["objects"]:
            obj = room["objects"][alias_tgt]
            if obj.get("hidden", False) and not include_hidden: return None
            if player and not self._can_see_object(obj, player): return None
            return alias_tgt
        return None

    def _resolve_inventory_item(self, player: Player, item_name: str) -> str | None:
        norm = self._normalize_text(item_name)
        for item in player.inventory:
            if self._normalize_text(item) == norm: return item
        alias_tgt = self._alias_for(item_name)
        if alias_tgt and alias_tgt in player.inventory: return alias_tgt
        return None

    def _find_object(self, room: dict, name: str, player: Player = None) -> tuple[str | None, dict | None]:
        obj_key = self._resolve_object_key(room, name, include_hidden=False, player=player)
        if not obj_key: return None, None
        obj = room["objects"].get(obj_key)
        if obj and not obj.get("hidden", False): return obj_key, obj
        return None, None

    def _make_room_update(self, room_key: str, viewer: Player = None) -> bytes:
        room = self.room_states[room_key]
        vis_objs = [n for n, obj in room["objects"].items() if not obj.get("hidden", False) and (viewer is None or self._can_see_object(obj, viewer))]
        players_here = [p.username for p in self.players.values() if p.current_room == room_key]
        exits_info = {dir: {"locked": data.get("locked", False), "room": data["room"]} for dir, data in room.get("exits", {}).items()}
        return make_room_update({"name": room_key, "exits": exits_info}, vis_objs, players_here)

    def initial_room_update(self, room_key: str, viewer: Player = None) -> bytes:
        return self._make_room_update(room_key, viewer)