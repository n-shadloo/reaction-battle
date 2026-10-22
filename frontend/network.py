import queue
import socket
import threading
from shared.constants import (
    JOIN_MSG, CLICK_MSG, CREATE_LOBBY_MSG, LIST_LOBBIES_MSG,
    LEAVE_SESSION_MSG, LEAVE_MSG, DISCONNECTED_MSG
)
from shared.protocol import Connection


class NetworkClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.connection: Connection | None = None
        self.incoming_messages: queue.Queue = queue.Queue()
        self.error = ''

        self._reader_thread: threading.Thread | None = None
        self._is_running = False

    def connect(self) -> bool:
        try:
            client_socket = socket.create_connection((self.host, self.port), timeout=5)
        except OSError as error:
            self.error = f'Could not connect: {error}'
            return False

        client_socket.settimeout(None)
        self.connection = Connection(client_socket)
        self._is_running = True

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        return True

    def _read_loop(self) -> None:
        while self._is_running and self.connection is not None and not self.connection.closed:
            for message in self.connection.receive():
                self.incoming_messages.put(message)

            if self.connection.closed:
                break

        self.incoming_messages.put({'type': DISCONNECTED_MSG})

    def drain_incoming(self) -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(self.incoming_messages.get_nowait())
            except queue.Empty:
                return messages

    def _send(self, message_type: str, **fields) -> None:
        if self.connection is not None:
            self.connection.send(message_type, **fields)

    def request_lobbies(self) -> None:
        self._send(LIST_LOBBIES_MSG)

    def create_lobby(self, name: str, capacity: int, duration_seconds: int) -> None:
        self._send(
            CREATE_LOBBY_MSG,
            name=name,
            capacity=capacity,
            duration_seconds=duration_seconds,
        )

    def join(self, name: str, session_id: str, spectator: bool = False) -> None:
        self._send(JOIN_MSG, name=name, session_id=session_id, spectator=spectator)

    def send_click(self, x: int, y: int) -> None:
        self._send(CLICK_MSG, x=x, y=y)

    def leave_session(self) -> None:
        self._send(LEAVE_SESSION_MSG)

    def leave(self) -> None:
        self._send(LEAVE_MSG)

    def close(self) -> None:
        self._is_running = False
        if self.connection is not None:
            self.connection.close()
