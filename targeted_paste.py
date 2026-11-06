"""Paste into one local core terminal without submitting or following UI focus.

Protocol: herdr-core wire.rs, generation negotiated by hello, framed attach.
Unsupported cores or terminals without bracketed-paste mode fall back to clipboard.
"""
import json
import os
import select
import struct
import subprocess
import time


class PasteUnavailable(RuntimeError):
    pass


class PasteConnection:
    def __init__(self, terminal):
        self.process = None
        self.channel = None
        if not terminal or '/' in terminal:
            raise PasteUnavailable('Only local terminals support targeted paste')
        try:
            info = json.loads(subprocess.run(['hc', 'get', terminal, '--json'], check=True,
                capture_output=True, text=True, timeout=4).stdout)
            if info.get('state') != 'live':
                raise PasteUnavailable('Terminal is no longer live')
            self.process = subprocess.Popen(['hc', 'connect'], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            self.deadline = time.monotonic() + 4
            request = {'jsonrpc': '2.0', 'id': 1, 'method': 'hello', 'params': {'framed': True}}
            self.process.stdin.write((json.dumps(request) + '\n').encode())
            line = bytearray()
            while not line.endswith(b'\n'):
                line.extend(self.read(1))
                if len(line) > 1024 * 1024:
                    raise PasteUnavailable('Invalid handshake')
            hello = json.loads(line)
            if 'error' in hello:
                raise PasteUnavailable('Core handshake failed')
            self.send(0, 0, json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'terminal.attach',
                'params': {'terminal': terminal, 'cols': info['cols'], 'rows': info['rows'],
                           'observe': False, 'history': 0}}).encode())
            bracketed = False
            paint = bytearray()
            while self.channel is None or not bracketed:
                channel, kind, payload = self.frame()
                if channel == 0 and kind == 0:
                    reply = json.loads(payload)
                    if reply.get('id') == 2:
                        if 'error' in reply:
                            raise PasteUnavailable('Attach failed')
                        self.channel = reply['result']['channel']
                elif kind == 0:
                    paint.extend(payload)
                    # Repaint advertises the terminal's current modes.
                    if len(paint) > 1024 * 1024:
                        raise PasteUnavailable('No bracketed paste mode')
                    bracketed = b'\x1b[?2004h' in paint
                elif kind == 2:
                    raise PasteUnavailable('Terminal closed')
        except Exception as exc:
            self.close()
            if isinstance(exc, PasteUnavailable):
                raise
            raise PasteUnavailable('Targeted paste is unavailable') from exc

    def read(self, count):
        data = bytearray()
        while len(data) < count:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise PasteUnavailable('Core response timed out')
            chunk = os.read(self.process.stdout.fileno(), count - len(data))
            if not chunk:
                raise PasteUnavailable('Core connection closed')
            data.extend(chunk)
        return bytes(data)

    def frame(self):
        channel, kind, size = struct.unpack('<IBI', self.read(9))
        if size > 16 * 1024 * 1024:
            raise PasteUnavailable('Invalid core frame')
        return channel, kind, self.read(size)

    def send(self, channel, kind, payload):
        data = struct.pack('<IBI', channel, kind, len(payload)) + payload
        fd = self.process.stdin.fileno()
        # Writes are bounded; callers only hold the session lock for final input.
        deadline = time.monotonic() + 0.5
        os.set_blocking(fd, False)
        while data:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                raise PasteUnavailable('Core input timed out')
            try:
                n = os.write(fd, data)
                data = data[n:]
            except BlockingIOError:
                continue

    def paste(self, text):
        # Never transmit terminal control bytes from speech or replacement rules.
        clean = ''.join(c for c in text if c >= ' ' or c in '\n\t')
        if len(clean.encode()) > 128 * 1024:
            raise PasteUnavailable('Transcript too large for automatic paste')
        self.send(self.channel, 0, b'\x1b[200~' + clean.encode() + b'\x1b[201~')

    def flush(self):
        # Ordered RPC barrier confirms the connection accepted preceding frames.
        self.deadline = time.monotonic() + 3
        self.send(0, 0, json.dumps({'jsonrpc': '2.0', 'id': 3, 'method': 'server.status', 'params': {}}).encode())
        while True:
            channel, kind, payload = self.frame()
            if channel == 0 and kind == 0 and json.loads(payload).get('id') == 3:
                return
            if channel == self.channel and kind == 2:
                raise PasteUnavailable('Terminal closed during paste')

    def close(self):
        if self.process:
            if self.channel is not None:
                try:
                    self.send(self.channel, 2, b'')
                except (OSError, PasteUnavailable):
                    pass
            self.process.stdin.close()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process.stdout.close()
            self.process = None
