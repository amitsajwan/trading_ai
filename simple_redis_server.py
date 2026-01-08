"""Simple in-memory Redis-like server for local development.

This provides basic Redis functionality without requiring Redis installation.
"""

import socket
import threading
import time
from typing import Dict, Any
import json


class SimpleRedisServer:
    """Simple in-memory Redis-like server."""

    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port
        self.data: Dict[str, Any] = {}
        self.expirations: Dict[str, float] = {}
        self.running = False
        self.server_socket = None

    def start(self):
        """Start the Redis-like server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        print(f"Simple Redis server started on {self.host}:{self.port}")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()
            except OSError:
                break

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def handle_client(self, client_socket):
        """Handle client connections."""
        buffer = b""

        while self.running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break

                buffer += data

                # Simple Redis protocol parsing (very basic)
                if b"\r\n" in buffer:
                    command = buffer.decode().strip()
                    buffer = b""

                    response = self.process_command(command)
                    client_socket.send(response.encode() + b"\r\n")

            except Exception as e:
                print(f"Client error: {e}")
                break

        client_socket.close()

    def process_command(self, command: str) -> str:
        """Process Redis commands."""
        parts = command.upper().split()
        if not parts:
            return "-ERR empty command"

        cmd = parts[0]

        if cmd == "PING":
            return "+PONG"

        elif cmd == "SET" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            self.data[key] = value
            # Remove expiration if exists
            self.expirations.pop(key, None)
            return "+OK"

        elif cmd == "GET" and len(parts) >= 2:
            key = parts[1]
            # Check expiration
            if key in self.expirations and time.time() > self.expirations[key]:
                self.data.pop(key, None)
                self.expirations.pop(key, None)
                return "$-1"

            value = self.data.get(key)
            if value is None:
                return "$-1"
            return f"${len(str(value))}\r\n{value}"

        elif cmd == "DEL" and len(parts) >= 2:
            key = parts[1]
            if key in self.data:
                self.data.pop(key, None)
                self.expirations.pop(key, None)
                return ":1"
            return ":0"

        elif cmd == "KEYS" and len(parts) >= 2:
            pattern = parts[1]
            if pattern == "*":
                keys = list(self.data.keys())
            else:
                # Simple pattern matching
                keys = [k for k in self.data.keys() if pattern in k]
            return f"*{len(keys)}\r\n" + "\r\n".join(f"${len(k)}\r\n{k}" for k in keys)

        elif cmd == "EXISTS" and len(parts) >= 2:
            key = parts[1]
            return ":1" if key in self.data else ":0"

        return "-ERR unknown command"


if __name__ == "__main__":
    server = SimpleRedisServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("Server stopped")
    finally:
        server.stop()
