"""
BT Keyboard — Linux Appliance Receiver

Runs as PID-1-adjacent daemon inside the custom appliance OS built from
custom-os/buildroot (see custom-os/README.md). It turns the machine into
a dedicated BT-Keyboard TCP receiver: a virtual USB keyboard is created
via /dev/uinput and fed the keystrokes received from the Android sender
app, using the exact same wire protocol as
desktop-receiver/receiver_wifi.py (newline-delimited JSON on TCP :9876).

Requires: python3-evdev (see requirements.txt), the `uinput` kernel
module loaded, and write access to /dev/uinput (root, or a member of the
`input` group with the udev rule installed by the buildroot package).
"""

import json
import logging
import signal
import socket
import sys
import threading

from keymap import (
    all_key_names,
    build_chords,
    resolve_combo_key,
    resolve_modifier,
    resolve_special,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("bt_keyboard")

PORT = 9876


# ═══════════════════════════════════════════════════════════════
#  KEY INJECTION (via /dev/uinput)
# ═══════════════════════════════════════════════════════════════

class KeyInjector:
    """Executes chords/messages against a uinput-style device.

    `device` must expose `emit(key_const, value)`. `resolver(key_name)`
    maps our string key names (e.g. "KEY_A") to whatever `device.emit`
    expects; defaults to looking the name up in `evdev.ecodes`.
    """

    def __init__(self, device, resolver=None):
        self.device = device
        if resolver is None:
            from evdev import ecodes
            resolver = lambda name: getattr(ecodes, name)
        self._resolve = resolver

    def _press(self, key_name):
        self.device.emit(self._resolve(key_name), 1)

    def _release(self, key_name):
        self.device.emit(self._resolve(key_name), 0)

    def _tap_chord(self, chord):
        for key in chord:
            self._press(key)
        for key in reversed(chord):
            self._release(key)

    def type_text(self, text):
        for chord in build_chords(text):
            self._tap_chord(chord)

    def inject(self, msg):
        """Process one decoded protocol message."""
        modifiers = msg.get("modifiers", [])
        held = []
        for name in modifiers:
            key = resolve_modifier(name)
            if key:
                self._press(key)
                held.append(key)

        try:
            msg_type = msg.get("type", "")
            value = msg.get("value", "")

            if msg_type in ("unicode", "key"):
                self.type_text(value)
            elif msg_type == "special":
                key = resolve_special(str(value).lower())
                if key:
                    self._tap_chord([key])
            elif msg_type == "combo":
                if isinstance(value, list):
                    combo = [resolve_combo_key(k.lower()) for k in value]
                    combo = [k for k in combo if k]
                    self._tap_chord(combo)
        finally:
            for key in reversed(held):
                self._release(key)


class _EvdevDeviceAdapter:
    """Adapts evdev.UInput's write/syn API to the emit(key, value) shape
    KeyInjector expects."""

    def __init__(self, ui, ecodes):
        self._ui = ui
        self._ecodes = ecodes

    def emit(self, key_code, value):
        self._ui.write(self._ecodes.EV_KEY, key_code, value)
        self._ui.syn()


def make_device():
    from evdev import UInput, ecodes
    capabilities = {ecodes.EV_KEY: [getattr(ecodes, name) for name in all_key_names()]}
    ui = UInput(capabilities, name="BT Keyboard Receiver")
    return _EvdevDeviceAdapter(ui, ecodes)


# ═══════════════════════════════════════════════════════════════
#  TCP SERVER — Receives keystrokes over WiFi
# ═══════════════════════════════════════════════════════════════

class TcpReceiver:
    """TCP server that listens for keystroke JSON messages from the phone."""

    def __init__(self, injector, port=PORT):
        self.injector = injector
        self.port = port
        self.running = False
        self.clients = []
        self.keystroke_count = 0

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(1.0)

        try:
            server.bind(("0.0.0.0", self.port))
            server.listen(5)
            logger.info(f"TCP server listening on port {self.port}")

            while self.running:
                try:
                    client, addr = server.accept()
                    logger.info(f"Client connected from {addr[0]}:{addr[1]}")
                    self.clients.append(client)
                    thread = threading.Thread(target=self._handle_client, args=(client, addr), daemon=True)
                    thread.start()
                except socket.timeout:
                    continue
        finally:
            server.close()

    def _handle_client(self, client, addr):
        buffer = ""
        try:
            while self.running:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        msg = json.loads(line)
                        self.keystroke_count += 1
                        self.injector.inject(msg)

                        t = msg.get("type", "")
                        v = msg.get("value", "")
                        if t in ("unicode", "key"):
                            print(v, end="", flush=True)
                        elif t == "special":
                            print(f" [{v}] ", end="", flush=True)
                    except json.JSONDecodeError:
                        pass

        except (ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            logger.info(f"Client {addr[0]} disconnected")
            client.close()
            if client in self.clients:
                self.clients.remove(client)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    local_ip = get_local_ip()

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║           ⌨  BT Keyboard Appliance                  ║")
    print("║                                                      ║")
    print(f"║  IP Address: {local_ip:<40}║")
    print(f"║  Port:       {PORT:<40}║")
    print("║                                                      ║")
    print("║  On your phone app, connect to the IP above.         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    try:
        device = make_device()
    except Exception as exc:
        logger.error(
            "Could not open /dev/uinput (%s). Make sure the `uinput` kernel "
            "module is loaded and this process has permission to write to "
            "/dev/uinput.", exc,
        )
        sys.exit(1)

    injector = KeyInjector(device)
    tcp = TcpReceiver(injector, port=PORT)
    tcp.start()

    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    stop_event.wait()
    tcp.stop()


if __name__ == "__main__":
    main()
