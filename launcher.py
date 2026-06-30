#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Launcher com auto-descoberta via UDP broadcast
#  Uso: python3 launcher.py
# ─────────────────────────────────────────────────────────────────
import socket
import threading
import time
import sys
import os

# ── Portas ───────────────────────────────────────────────────────
GAME_PORT       = 5000   # TCP — jogo em si
DISCOVERY_PORT  = 5001   # UDP — auto-descoberta na LAN

DISCOVERY_MSG    = "ESCAPE_ROOM_ERP1"   # identificador do broadcast
DISCOVERY_INTERVAL = 2   # segundos entre broadcasts do servidor
DISCOVERY_TIMEOUT  = 6   # segundos que o cliente espera pelo broadcast

# ─────────────────────────────────────────────────────────────────
#  Utilitários de rede
# ─────────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """Detecta o IP local usando conexão UDP fictícia (não envia pacotes)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def broadcast_presence(local_ip: str, game_port: int, stop_event: threading.Event):
    """
    Servidor: envia broadcast UDP na LAN a cada DISCOVERY_INTERVAL segundos.
    Payload: 'ESCAPE_ROOM_ERP1:<ip>:<port>'
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    message = f"{DISCOVERY_MSG}:{local_ip}:{game_port}".encode("utf-8")

    while not stop_event.is_set():
        try:
            sock.sendto(message, ("<broadcast>", DISCOVERY_PORT))
        except Exception:
            pass
        time.sleep(DISCOVERY_INTERVAL)

    sock.close()


def discover_server(timeout: int = DISCOVERY_TIMEOUT) -> tuple[str, int] | None:
    """
    Cliente: escuta broadcasts UDP por 'timeout' segundos.
    Retorna (host, port) se achar o servidor, ou None.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)  # timeout por recv (loop interno)

    try:
        sock.bind(("", DISCOVERY_PORT))
    except OSError:
        # Porta ocupada (talvez o próprio servidor local)
        sock.close()
        return None

    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        sys.stdout.write(f"\r  🔍 Procurando servidor na rede... ({remaining}s) ")
        sys.stdout.flush()
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8").strip()
            if msg.startswith(DISCOVERY_MSG + ":"):
                parts = msg.split(":")
                host = parts[1]
                port = int(parts[2])
                sock.close()
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
                return host, port
        except socket.timeout:
            continue
        except Exception:
            break

    sock.close()
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
    return None


# ─────────────────────────────────────────────────────────────────
#  Opção 1 — Criar partida (este PC vira host + jogador)
# ─────────────────────────────────────────────────────────────────

def criar_partida():
    from server import Server
    from client import main as run_client

    local_ip = get_local_ip()

    # Sobe servidor em thread daemon
    server = Server("0.0.0.0", GAME_PORT)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # aguarda o servidor estar pronto para aceitar

    # Inicia broadcast de descoberta
    stop_broadcast = threading.Event()
    broadcast_thread = threading.Thread(
        target=broadcast_presence,
        args=(local_ip, GAME_PORT, stop_broadcast),
        daemon=True
    )
    broadcast_thread.start()

    print(f"\n{'═'*56}")
    print(f"  ✅ Servidor iniciado!")
    print(f"{'─'*56}")
    print(f"  📡 Transmitindo presença na rede local automaticamente.")
    print(f"     Os outros jogadores só precisam escolher")
    print(f"     'Entrar em partida' — sem digitar IP.")
    print(f"{'─'*56}")
    print(f"  🌐 IP (caso precise conectar manualmente): {local_ip}")
    print(f"{'═'*56}\n")

    # Conecta o jogador local como cliente em localhost
    # Sobrescreve sys.argv para o client usar localhost
    sys.argv = ["client.py", "--host", "127.0.0.1", "--port", str(GAME_PORT)]

    try:
        run_client()
    finally:
        stop_broadcast.set()


# ─────────────────────────────────────────────────────────────────
#  Opção 2 — Entrar em partida (auto-descoberta ou IP manual)
# ─────────────────────────────────────────────────────────────────

def entrar_partida():
    from client import main as run_client

    print()
    result = discover_server(timeout=DISCOVERY_TIMEOUT)

    if result:
        host, port = result
        print(f"  ✅ Servidor encontrado automaticamente: {host}:{port}")
        sys.argv = ["client.py", "--host", host, "--port", str(port)]
    else:
        print(f"  ⚠️  Nenhum servidor encontrado na rede.")
        print(f"  Digite o IP manualmente (ou Enter para localhost):")
        sys.stdout.write("  IP: ")
        sys.stdout.flush()
        ip_input = input().strip()
        host = ip_input if ip_input else "127.0.0.1"
        sys.argv = ["client.py", "--host", host, "--port", str(GAME_PORT)]
        print(f"  Conectando em {host}:{GAME_PORT}...")

    print()
    run_client()


# ─────────────────────────────────────────────────────────────────
#  Menu principal
# ─────────────────────────────────────────────────────────────────

def menu():
    print(f"\n{'╔'+'═'*48+'╗'}")
    print(f"║{'  🚪  ESCAPE ROOM  —  ERP/1.0':^48}║")
    print(f"{'╠'+'═'*48+'╣'}")
    print(f"║{'':48}║")
    print(f"║  {'1. Criar partida':46}║")
    print(f"║  {'   (este PC vira host e entra como jogador)':46}║")
    print(f"║{'':48}║")
    print(f"║  {'2. Entrar em partida':46}║")
    print(f"║  {'   (busca servidor automaticamente na rede)':46}║")
    print(f"║{'':48}║")
    print(f"{'╚'+'═'*48+'╝'}")

    while True:
        sys.stdout.write("\n  Escolha (1 ou 2): ")
        sys.stdout.flush()
        choice = input().strip()

        if choice == "1":
            criar_partida()
            break
        elif choice == "2":
            entrar_partida()
            break
        else:
            print("  ❌ Opção inválida. Digite 1 ou 2.")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\n\n[Saindo...]")
