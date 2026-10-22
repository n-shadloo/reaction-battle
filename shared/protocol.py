import json
import socket
from shared.constants import BUFFER_SIZE, MESSAGE_END


def encode_message(message_type: str, **fields) -> bytes:
    data = {'type': message_type}
    data.update(fields)
    return (json.dumps(data) + MESSAGE_END).encode('utf-8')


class Connection:
    def __init__(self, client_socket: socket.socket):
        self.client_socket = client_socket
        self._buffer = ''
        self.closed = False

    def send(self, message_type: str, **fields) -> bool:
        if self.closed:
            return False

        try:
            self.client_socket.sendall(encode_message(message_type, **fields))
            return True
        except OSError:
            self.closed = True
            return False

    def receive(self) -> list[dict]:
        if self.closed:
            return []

        try:
            chunk = self.client_socket.recv(BUFFER_SIZE)
        except OSError:
            self.closed = True
            return []

        if not chunk:
            self.closed = True
            return []

        self._buffer += chunk.decode('utf-8', errors='ignore')

        messages = []
        while MESSAGE_END in self._buffer:
            line, self._buffer = self._buffer.split(MESSAGE_END, 1)
            line = line.strip()
            if not line:
                continue

            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return messages

    def close(self) -> None:
        self.closed = True
        try:
            self.client_socket.close()
        except OSError:
            pass
