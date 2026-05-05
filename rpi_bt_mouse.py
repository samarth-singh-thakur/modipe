#!/usr/bin/env python3
"""
Use a Raspberry Pi as a Bluetooth HID mouse for an Android phone.

Run this over SSH on the Pi, pair the Android phone with the Pi, then use:
  Arrow keys  - move pointer
  Space/Enter - left click
  r           - right click
  w/s         - scroll up/down
  q           - quit

Requires Raspberry Pi OS with BlueZ.
"""

import os
import select
import shutil
import socket
import struct
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Optional


P_CTRL = 0x11
P_INTR = 0x13


def run(*args: str) -> None:
    subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def configure_adapter(name: str) -> None:
    run("sudo", "hciconfig", "hci0", "up")
    run("sudo", "btmgmt", "power", "on")
    run("sudo", "btmgmt", "connectable", "on")
    run("sudo", "btmgmt", "pairable", "on")
    run("sudo", "btmgmt", "bredr", "on")
    run("sudo", "btmgmt", "le", "off")
    run("sudo", "bluetoothctl", "system-alias", name)
    run("sudo", "bluetoothctl", "discoverable", "on")


def register_sdp_service() -> bool:
    if shutil.which("sdptool") is None:
        print("Missing sdptool. Install it with: sudo apt install bluez", file=sys.stderr)
        return False

    result = subprocess.run(
        ["sdptool", "add", "--handle=0x10000", "HID"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode == 0:
        print("Registered Bluetooth HID SDP record.")
        return True

    print(result.stdout.strip(), file=sys.stderr)
    print("Could not register the HID SDP record.", file=sys.stderr)
    print("Make sure bluetoothd is running with --compat --noplugin=input.", file=sys.stderr)
    return False


def l2cap_server(psm: int) -> socket.socket:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", psm))
    except OSError as exc:
        raise OSError(
            f"Could not bind Bluetooth L2CAP PSM 0x{psm:02x}. "
            "Another Bluetooth HID/input service may already be using it."
        ) from exc
    sock.listen(1)
    return sock


@dataclass
class MouseState:
    interrupt: Optional[socket.socket] = None
    speed: int = 12

    def send_report(self, buttons: int = 0, dx: int = 0, dy: int = 0, wheel: int = 0) -> None:
        if self.interrupt is None:
            return
        dx = max(-127, min(127, dx))
        dy = max(-127, min(127, dy))
        wheel = max(-127, min(127, wheel))
        report = struct.pack("!BBbbb", 0xA1, buttons & 0x07, dx, dy, wheel)
        self.interrupt.send(report)

    def click(self, button: int) -> None:
        self.send_report(buttons=button)
        self.send_report()


class RawTerminal:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


def read_key() -> str:
    ch = sys.stdin.read(1)
    if ch == "\x1b" and select.select([sys.stdin], [], [], 0.02)[0]:
        ch += sys.stdin.read(2)
    return ch


def accept_when_ready(server: socket.socket, label: str) -> socket.socket:
    print(f"Waiting for Android {label} channel...")
    client, address = server.accept()
    print(f"Connected {label} channel from {address[0]}")
    return client


def main() -> int:
    if os.geteuid() != 0:
        print("Run with sudo: sudo python3 rpi_bt_mouse.py", file=sys.stderr)
        return 1

    configure_adapter("Raspberry Pi Mouse")
    if not register_sdp_service():
        return 1

    try:
        control_server = l2cap_server(P_CTRL)
        interrupt_server = l2cap_server(P_INTR)
    except OSError as exc:
        print(exc, file=sys.stderr)
        print("BlueZ or another process is holding the HID mouse ports.", file=sys.stderr)
        print("Run the systemd override from README.md to start bluetoothd with --compat --noplugin=input.", file=sys.stderr)
        print("Then forget the Pi on Android and run this script again.", file=sys.stderr)
        return 1

    print()
    print("On Android: Settings > Bluetooth > Pair new device > Raspberry Pi Mouse")
    print("If Android already remembers this Pi, forget it first and pair again.")
    print()

    control = accept_when_ready(control_server, "control")
    interrupt = accept_when_ready(interrupt_server, "interrupt")
    state = MouseState(interrupt=interrupt)

    print()
    print("Ready. Arrow keys move, Space/Enter left-click, r right-click, w/s scroll, +/- speed, q quit.")

    with RawTerminal():
        while True:
            key = read_key()
            if key == "q":
                break
            if key == "\x1b[A":
                state.send_report(dy=-state.speed)
            elif key == "\x1b[B":
                state.send_report(dy=state.speed)
            elif key == "\x1b[C":
                state.send_report(dx=state.speed)
            elif key == "\x1b[D":
                state.send_report(dx=-state.speed)
            elif key in (" ", "\n", "\r"):
                state.click(1)
            elif key == "r":
                state.click(2)
            elif key == "w":
                state.send_report(wheel=1)
            elif key == "s":
                state.send_report(wheel=-1)
            elif key in ("+", "="):
                state.speed = min(60, state.speed + 2)
                print(f"\rSpeed {state.speed}   ", end="", flush=True)
            elif key in ("-", "_"):
                state.speed = max(2, state.speed - 2)
                print(f"\rSpeed {state.speed}   ", end="", flush=True)

    for sock in (control, interrupt, control_server, interrupt_server):
        try:
            sock.close()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
