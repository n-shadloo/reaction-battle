import argparse
import socket
import threading
import time
import uuid
from shared.constants import (
    DEFAULT_HOST, DEFAULT_PORT, PLAYER, SPECTATOR,
    ACCEPT_TIMEOUT_SECONDS, BROADCAST_INTERVAL_SECONDS,
    LOBBY_CAPACITY_CHOICES, DEFAULT_LOBBY_CAPACITY,
    ROUND_DURATION_CHOICES, DEFAULT_ROUND_SECONDS,
    WAITING_PHASE, COUNTDOWN_PHASE, PLAYING_PHASE, FINISHED_PHASE,
    CLICK_MSG, LIST_LOBBIES_MSG, CREATE_LOBBY_MSG, JOIN_MSG,
    LEAVE_SESSION_MSG, LEAVE_MSG,
    JOINED_MSG, LOBBIES_MSG, STATE_MSG, GAME_OVER_MSG, ERROR_MSG
)
from shared.protocol import Connection
from game.session import GameSession


def current_time_ms() -> int:
    return int(time.time() * 1000)


class ClientHandle:
    def __init__(self, connection: Connection, address):
        self.connection = connection
        self.address = address
        self.name = ''
        self.role = PLAYER
        self.session_id = ''
        self.player_id = ''
        self.alive = True


class Server:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port

        self.server_socket: socket.socket | None = None
        self.running = False

        self.clients: dict[str, ClientHandle] = {}
        self.sessions: dict[str, GameSession] = {}

        self._lock = threading.Lock()

    def bind(self) -> int:
        if self.server_socket is not None:
            return self.port

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.server_socket.settimeout(ACCEPT_TIMEOUT_SECONDS)
        self.port = self.server_socket.getsockname()[1]
        return self.port

    def start(self) -> None:
        self.bind()
        self.running = True

        print(f'Server listening on {self.host}:{self.port}')

        threading.Thread(target=self._broadcast_loop, daemon=True).start()

        try:
            self._accept_loop()
        except KeyboardInterrupt:
            print('\nShutting down...')
        finally:
            self.stop()

    def stop(self) -> None:
        self.running = False
        with self._lock:
            for client in list(self.clients.values()):
                client.connection.close()

        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass

    def _accept_loop(self) -> None:
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            client = ClientHandle(Connection(client_socket), address)
            client_id = uuid.uuid4().hex
            with self._lock:
                self.clients[client_id] = client

            threading.Thread(
                target=self._client_loop,
                args=(client_id, client),
                daemon=True,
            ).start()

    def _client_loop(self, client_id: str, client: ClientHandle) -> None:
        self._send_lobby_list(client)

        while self.running and client.alive and not client.connection.closed:
            messages = client.connection.receive()
            if client.connection.closed:
                break

            for message in messages:
                self._handle_message(client_id, client, message)

        self._drop_client(client_id, client)

    def _drop_client(self, client_id: str, client: ClientHandle) -> None:
        with self._lock:
            client.alive = False
            self.clients.pop(client_id, None)

        self._leave_current_session(client, keep_for_results=True)
        client.connection.close()

    def _handle_message(self, client_id: str, client: ClientHandle, message: dict) -> None:
        message_type = message.get('type', '')

        if message_type == LIST_LOBBIES_MSG:
            self._send_lobby_list(client)
        elif message_type == CREATE_LOBBY_MSG:
            self._create_lobby(client, message)
        elif message_type == JOIN_MSG:
            self._join_lobby(client, message)
        elif message_type == CLICK_MSG:
            self._on_click(client, message)
        elif message_type == LEAVE_SESSION_MSG:
            self._leave_current_session(client, keep_for_results=False)
            self._send_lobby_list(client)
        elif message_type == LEAVE_MSG:
            self._drop_client(client_id, client)

    def _leave_current_session(self, client: ClientHandle, keep_for_results: bool) -> None:
        session_id = client.session_id
        client.session_id = ''

        session = self.sessions.get(session_id)
        if session is None:
            return

        keeps_score = (
            keep_for_results and
            client.role == PLAYER and
            session.phase == PLAYING_PHASE
        )
        if keeps_score:
            session.mark_disconnected(client.player_id)
        else:
            session.remove_participant(client.player_id)

        self._delete_unused_session(session_id)

    def _delete_unused_session(self, session_id: str) -> None:
        with self._lock:
            still_watched = any(
                client.session_id == session_id
                for client in self.clients.values()
            )
            if not still_watched:
                self.sessions.pop(session_id, None)

    def _create_lobby(self, client: ClientHandle, message: dict) -> None:
        name = str(message.get('name', 'Player')).strip() or 'Player'

        capacity = message.get('capacity', DEFAULT_LOBBY_CAPACITY)
        if capacity not in LOBBY_CAPACITY_CHOICES:
            capacity = DEFAULT_LOBBY_CAPACITY

        duration_seconds = message.get('duration_seconds', DEFAULT_ROUND_SECONDS)
        if duration_seconds not in ROUND_DURATION_CHOICES:
            duration_seconds = DEFAULT_ROUND_SECONDS

        self._leave_current_session(client, keep_for_results=False)

        session_id = uuid.uuid4().hex[:6]
        session = GameSession(session_id, name, capacity, duration_seconds)
        with self._lock:
            self.sessions[session_id] = session

        player_id = uuid.uuid4().hex
        slot = session.add_player(name, player_id, current_time_ms())

        client.name = name
        client.role = PLAYER
        client.session_id = session_id
        client.player_id = player_id

        client.connection.send(
            JOINED_MSG,
            session_id=session_id,
            role=PLAYER,
            slot=slot,
            player_id=player_id,
        )

    def _join_lobby(self, client: ClientHandle, message: dict) -> None:
        name = str(message.get('name', 'Player')).strip() or 'Player'
        session_id = str(message.get('session_id', ''))
        wants_to_spectate = bool(message.get('spectator', False))

        session = self.sessions.get(session_id)
        if session is None:
            client.connection.send(ERROR_MSG, reason='That lobby does not exist.')
            return

        self._leave_current_session(client, keep_for_results=False)

        participant_id = uuid.uuid4().hex
        client.name = name
        client.player_id = participant_id

        if wants_to_spectate:
            session.add_spectator(name, participant_id)
            client.role = SPECTATOR
            client.session_id = session_id
            client.connection.send(
                JOINED_MSG,
                session_id=session_id,
                role=SPECTATOR,
                slot=-1,
                player_id=participant_id,
            )
            return

        slot = session.add_player(name, participant_id, current_time_ms())
        if slot < 0:
            client.connection.send(ERROR_MSG, reason='That lobby is full.')
            return

        client.role = PLAYER
        client.session_id = session_id
        client.connection.send(
            JOINED_MSG,
            session_id=session_id,
            role=PLAYER,
            slot=slot,
            player_id=participant_id,
        )

    def _on_click(self, client: ClientHandle, message: dict) -> None:
        if client.role != PLAYER:
            return

        session = self.sessions.get(client.session_id)
        if session is None:
            return

        session.handle_click(
            client.player_id,
            int(message.get('x', 0)),
            int(message.get('y', 0)),
            current_time_ms(),
        )

    def _open_lobbies(self) -> list[dict]:
        return [
            {
                'id': session.session_id,
                'host': session.host_name,
                'players': len(session.players),
                'capacity': session.capacity,
                'duration_seconds': session.duration_seconds,
                'phase': session.phase,
            }
            for session in list(self.sessions.values())
            if session.phase in (WAITING_PHASE, COUNTDOWN_PHASE)
        ]

    def _send_lobby_list(self, client: ClientHandle) -> None:
        client.connection.send(LOBBIES_MSG, lobbies=self._open_lobbies())

    def _broadcast_loop(self) -> None:
        while self.running:
            now = current_time_ms()

            for session in list(self.sessions.values()):
                session.update(now)

            with self._lock:
                clients = list(self.clients.values())

            for client in clients:
                if not client.session_id:
                    continue

                session = self.sessions.get(client.session_id)
                if session is None:
                    continue

                viewer_id = client.player_id if client.role == PLAYER else None
                state_snapshot = session.snapshot(now, viewer_id)
                if session.phase == FINISHED_PHASE:
                    client.connection.send(GAME_OVER_MSG, state=state_snapshot)
                else:
                    client.connection.send(STATE_MSG, state=state_snapshot)

            time.sleep(BROADCAST_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description='Reaction Battle server')
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help='use 0.0.0.0 to accept players from other machines')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    Server(args.host, args.port).start()


if __name__ == '__main__':
    main()
