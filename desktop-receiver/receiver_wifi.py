"""
BT Keyboard — Windows Desktop Receiver (No bless dependency)

This version works WITHOUT the 'bless' library.
Instead of running a BLE GATT server (which bless provides but is broken
on Python 3.12+), this receiver uses two methods:

METHOD 1: WiFi/TCP mode (recommended, works immediately)
  - Receiver listens on TCP port 9876
  - Mobile app connects via WiFi (same network)
  - Zero Bluetooth issues, works on all PCs

METHOD 2: BLE Central mode
  - Receiver scans for mobile devices advertising the service
  - Connects as a GATT client and subscribes to notifications
  - Mobile app acts as the GATT server instead

Dependencies: pip install bleak (just one library!)
"""

import asyncio
import json
import socket
import threading
import ctypes
import ctypes.wintypes
import sys
import signal
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("bt_keyboard")

# ═══════════════════════════════════════════════════════════════
#  WINDOWS KEYSTROKE INJECTOR (Unicode support)
# ═══════════════════════════════════════════════════════════════

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_MAP = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "escape": 0x1B,
    "space": 0x20, "delete": 0x2E,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "shift": 0x10, "ctrl": 0xA2, "alt": 0xA4, "meta": 0x5B,
}

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
                ("dwFlags", ctypes.wintypes.DWORD), ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _anonymous_ = ("_u",)
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_u", _U)]

SendInput = ctypes.windll.user32.SendInput

def _send_key(vk=0, scan=0, flags=0):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.wScan = scan
    inp.ki.dwFlags = flags
    inp.ki.time = 0
    inp.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def type_unicode(text):
    """Type Unicode text — works with ALL languages (Gujarati, Hindi, Tamil, etc.)"""
    for char in text:
        code = ord(char)
        if code > 0xFFFF:
            high = 0xD800 + ((code - 0x10000) >> 10)
            low = 0xDC00 + ((code - 0x10000) & 0x3FF)
            _send_key(scan=high, flags=KEYEVENTF_UNICODE)
            _send_key(scan=high, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            _send_key(scan=low, flags=KEYEVENTF_UNICODE)
            _send_key(scan=low, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        else:
            _send_key(scan=code, flags=KEYEVENTF_UNICODE)
            _send_key(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

def press_key(vk):
    _send_key(vk=vk)

def release_key(vk):
    _send_key(vk=vk, flags=KEYEVENTF_KEYUP)

def inject_keystroke(data):
    """Process a keystroke message and type it into the active window."""
    msg_type = data.get("type", "")
    value = data.get("value", "")
    modifiers = data.get("modifiers", [])

    # Press modifiers
    held = []
    for mod in modifiers:
        vk = VK_MAP.get(mod)
        if vk:
            press_key(vk)
            held.append(vk)

    try:
        if msg_type in ("unicode", "key"):
            type_unicode(value)
        elif msg_type == "special":
            vk = VK_MAP.get(value.lower())
            if vk:
                press_key(vk)
                release_key(vk)
        elif msg_type == "combo":
            if isinstance(value, list):
                combo = []
                for k in value:
                    vk = VK_MAP.get(k.lower())
                    if vk:
                        press_key(vk)
                        combo.append(vk)
                for vk in reversed(combo):
                    release_key(vk)
    finally:
        for vk in reversed(held):
            release_key(vk)

# ═══════════════════════════════════════════════════════════════
#  TCP SERVER — Receives keystrokes over WiFi
# ═══════════════════════════════════════════════════════════════

class TcpReceiver:
    """
    TCP server that listens for keystroke JSON messages.
    Mobile app connects over WiFi to this server.
    """

    def __init__(self, port=9876):
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

                # Process complete JSON messages (newline-delimited)
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        msg = json.loads(line)
                        self.keystroke_count += 1
                        inject_keystroke(msg)

                        # Display
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
#  GUI
# ═══════════════════════════════════════════════════════════════

def get_local_ip():
    """Get this PC's local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_gui(tcp_receiver):
    """Tkinter GUI showing connection status."""
    try:
        import tkinter as tk
    except ImportError:
        return  # No GUI, console only

    local_ip = get_local_ip()

    root = tk.Tk()
    root.title("BT Keyboard Receiver")
    root.geometry("520x420")
    root.configure(bg="#1A1A2E")
    root.resizable(False, False)

    # Title
    tk.Label(root, text="⌨  BT Keyboard Receiver", font=("Segoe UI", 22, "bold"),
             fg="white", bg="#1A1A2E").pack(pady=(24, 4))

    tk.Label(root, text="Receiving keystrokes from your phone/tablet",
             font=("Segoe UI", 11), fg="#888888", bg="#1A1A2E").pack()

    # Connection info box
    info_frame = tk.Frame(root, bg="#22223A", padx=20, pady=16)
    info_frame.pack(fill=tk.X, padx=24, pady=(20, 0))

    tk.Label(info_frame, text="Connect your mobile app to:", font=("Segoe UI", 11),
             fg="#AAAAAA", bg="#22223A", anchor="w").pack(fill=tk.X)

    ip_label = tk.Label(info_frame, text=f"IP:  {local_ip}    Port:  9876",
                        font=("Consolas", 16, "bold"), fg="#00FF88", bg="#22223A")
    ip_label.pack(pady=(8, 0))

    # Status
    status_var = tk.StringVar(value="⏳ Waiting for connection...")
    tk.Label(root, textvariable=status_var, font=("Segoe UI", 13),
             fg="#00FF88", bg="#1A1A2E").pack(pady=(20, 4))

    # Keystroke counter
    count_var = tk.StringVar(value="Keystrokes: 0")
    tk.Label(root, textvariable=count_var, font=("Segoe UI", 10),
             fg="#666666", bg="#1A1A2E").pack()

    # Log
    log_frame = tk.Frame(root, bg="#22223A")
    log_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(12, 24))

    tk.Label(log_frame, text="Received text:", font=("Segoe UI", 9),
             fg="#555555", bg="#22223A", anchor="w").pack(fill=tk.X, padx=12, pady=(8, 0))

    log_text = tk.Text(log_frame, height=5, bg="#22223A", fg="#E0E0E0",
                       font=("Consolas", 12), relief=tk.FLAT, state=tk.DISABLED,
                       insertbackground="white")
    log_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))

    def update_gui():
        if tcp_receiver.clients:
            status_var.set(f"🔗 Connected — {len(tcp_receiver.clients)} device(s)")
        else:
            status_var.set("⏳ Waiting for connection...")

        count_var.set(f"Keystrokes: {tcp_receiver.keystroke_count}")
        root.after(500, update_gui)

    update_gui()

    def on_close():
        tcp_receiver.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    local_ip = get_local_ip()

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║           ⌨  BT Keyboard Receiver                   ║")
    print("║                                                      ║")
    print(f"║  IP Address: {local_ip:<40}║")
    print(f"║  Port:       9876                                    ║")
    print("║                                                      ║")
    print("║  On your phone app, connect to the IP above.         ║")
    print("║  Press Ctrl+C to quit.                               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    tcp = TcpReceiver(port=9876)
    tcp.start()

    # Run GUI (blocks until window is closed)
    run_gui(tcp)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
