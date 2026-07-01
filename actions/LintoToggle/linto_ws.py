"""Minimal WebSocket client for the gnome-linto control server.

Uses only the Python standard library (no third-party packages), so the plugin
needs nothing installed. Runs in a background thread, parses status JSON, sends
commands, and reconnects on failure.
"""

import base64
import json
import os
import socket
import struct
import threading
import time


class _AuthError(Exception):
    pass


class LintoClient:
    def __init__(self, host, port, password, owner, dispatch):
        self.host = host
        self.port = int(port)
        self.password = password
        self._owner = owner                 # weakref.ref to the owning action
        self._dispatch = dispatch           # schedules fn(*args) on the UI thread
        self._sock = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def _emit(self, method_name, *args):
        # Resolve the owning action through a weak reference. If it has been
        # discarded (a page reload), shut this client down so it does not
        # linger as a zombie that keeps reconnecting and rendering.
        action = self._owner()
        if action is None:
            self._stop.set()
            self._close()
            return
        self._dispatch(getattr(action, method_name), *args)

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._close()

    def send_action(self, action):
        try:
            self._send(0x1, json.dumps({"action": action}).encode())
        except Exception:
            pass

    # -- internals ---------------------------------------------------------

    def _run(self):
        backoff = 1
        while not self._stop.is_set():
            try:
                self._connect()
                self._emit("_on_conn", True, "connected")
                backoff = 1
                self._read_loop()
            except _AuthError:
                self._emit("_on_conn", False, "auth")
                self._stop.wait(5)
            except Exception as exc:
                self._emit("_on_conn", False, str(exc))
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 15)
            finally:
                self._close()

    def _connect(self):
        sock = socket.create_connection((self.host, self.port), timeout=6)
        sock.settimeout(12)  # heartbeat arrives every ~5s, so this catches death
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET /?password=%s HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ) % (self.password, self.host, self.port, key)
        sock.sendall(req.encode())

        header = b""
        while b"\r\n\r\n" not in header:
            chunk = sock.recv(1)
            if not chunk:
                raise ConnectionError("no handshake response")
            header += chunk
        status_line = header.split(b"\r\n", 1)[0]
        if b"101" not in status_line:
            raise ConnectionError("handshake failed")
        self._sock = sock

    def _read_loop(self):
        got_status = False
        start = time.time()
        while not self._stop.is_set():
            opcode, payload = self._read_frame()
            if opcode is None or opcode == 0x8:  # closed / close frame
                # A prompt close with no status is how the server rejects a bad
                # password (it upgrades, then closes ~1s later).
                if not got_status and (time.time() - start) < 3:
                    raise _AuthError()
                raise ConnectionError("closed")
            if opcode == 0x9:  # ping -> pong
                self._send(0xA, payload)
            elif opcode == 0x1:  # text
                got_status = True
                try:
                    self._emit("_on_status", json.loads(payload.decode()))
                except Exception:
                    pass

    def _read_frame(self):
        head = self._recvn(2)
        if head is None:
            return None, None
        length = head[1] & 0x7F
        masked = head[1] & 0x80
        if length == 126:
            ext = self._recvn(2)
            if ext is None:
                return None, None
            length = struct.unpack(">H", ext)[0]
        elif length == 127:
            ext = self._recvn(8)
            if ext is None:
                return None, None
            length = struct.unpack(">Q", ext)[0]
        mask = self._recvn(4) if masked else b""
        payload = self._recvn(length) if length else b""
        if payload is None:
            return None, None
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return head[0] & 0x0F, payload

    def _recvn(self, n):
        data = b""
        while len(data) < n:
            try:
                chunk = self._sock.recv(n - len(data))
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def _send(self, opcode, data=b""):
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        length = len(data)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        with self._send_lock:
            if self._sock is not None:
                self._sock.sendall(bytes(header) + mask + masked)

    def _close(self):
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
