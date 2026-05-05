#!/usr/bin/env python3
"""
Use a Raspberry Pi as a Bluetooth HID mouse for an Android phone.

Run this over SSH on the Pi, pair the Android phone with the Pi, then use:
  Arrow keys  - move pointer
  Space/Enter - left click
  r           - right click
  w/s         - scroll up/down
  q           - quit

Requires Raspberry Pi OS with BlueZ and python3-dbus.
"""

import os
import select
import socket
import struct
import subprocess
import sys
import termios
import threading
import tty
from dataclasses import dataclass
from typing import Optional

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib


BLUEZ_SERVICE = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
PROFILE_PATH = "/com/example/btmouse/profile"
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"

P_CTRL = 0x11
P_INTR = 0x13

DBUS_LOOP = None
PROFILE_OBJECT = None


SERVICE_RECORD = """
<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <attribute id="0x0001">
    <sequence>
      <uuid value="0x1124" />
    </sequence>
  </attribute>
  <attribute id="0x0004">
    <sequence>
      <sequence>
        <uuid value="0x0100" />
      </sequence>
      <sequence>
        <uuid value="0x0011" />
        <uint16 value="0x0011" />
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0005">
    <sequence>
      <uuid value="0x1002" />
    </sequence>
  </attribute>
  <attribute id="0x0006">
    <sequence>
      <uint16 value="0x656e" />
      <uint16 value="0x006a" />
      <uint16 value="0x0100" />
    </sequence>
  </attribute>
  <attribute id="0x0009">
    <sequence>
      <sequence>
        <uuid value="0x1124" />
        <uint16 value="0x0100" />
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x000d">
    <sequence>
      <sequence>
        <sequence>
          <uuid value="0x0100" />
        </sequence>
        <sequence>
          <uuid value="0x0013" />
          <uint16 value="0x0013" />
        </sequence>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0100">
    <text value="Raspberry Pi SSH Mouse" />
  </attribute>
  <attribute id="0x0101">
    <text value="Keyboard controlled Bluetooth mouse" />
  </attribute>
  <attribute id="0x0102">
    <text value="Codex" />
  </attribute>
  <attribute id="0x0200">
    <uint16 value="0x0100" />
  </attribute>
  <attribute id="0x0201">
    <uint16 value="0x0111" />
  </attribute>
  <attribute id="0x0202">
    <uint8 value="0x40" />
  </attribute>
  <attribute id="0x0203">
    <uint8 value="0x21" />
  </attribute>
  <attribute id="0x0204">
    <boolean value="true" />
  </attribute>
  <attribute id="0x0205">
    <boolean value="true" />
  </attribute>
  <attribute id="0x0206">
    <sequence>
      <sequence>
        <uint8 value="0x22" />
        <text encoding="hex" value="05010902a1010901a100050919012903150025017503950581027501950381010501093009311581257f75089502810609381581257f750895018106c0c0" />
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0207">
    <sequence>
      <sequence>
        <uint16 value="0x0409" />
        <uint16 value="0x0100" />
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0209">
    <boolean value="true" />
  </attribute>
  <attribute id="0x020b">
    <uint16 value="0x0100" />
  </attribute>
  <attribute id="0x020c">
    <uint16 value="0x0c80" />
  </attribute>
</record>
"""


class HidProfile(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, PROFILE_PATH)

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, properties):
        # This program accepts L2CAP sockets itself. BlueZ may still call this
        # on some versions after profile registration; keeping the fd open is
        # enough for the host-side profile registration to remain happy.
        os.close(fd.take())

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        pass


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


def register_profile() -> None:
    global DBUS_LOOP, PROFILE_OBJECT

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    PROFILE_OBJECT = HidProfile(bus)
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE, "/org/bluez"), "org.bluez.ProfileManager1")
    opts = {
        "ServiceRecord": SERVICE_RECORD,
        "Role": "server",
        "RequireAuthentication": False,
        "RequireAuthorization": False,
        "AutoConnect": True,
    }
    try:
        manager.RegisterProfile(PROFILE_PATH, HID_UUID, opts)
    except dbus.exceptions.DBusException as exc:
        if exc.get_dbus_name() != "org.bluez.Error.NotPermitted" or "UUID already registered" not in str(exc):
            raise
        print("BlueZ already has a HID profile registered; continuing with the existing profile.")
        print("If the phone cannot pair, reboot the Pi or restart bluetooth, then run this script again.")
    DBUS_LOOP = GLib.MainLoop()
    threading.Thread(target=DBUS_LOOP.run, daemon=True).start()


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
    register_profile()

    try:
        control_server = l2cap_server(P_CTRL)
        interrupt_server = l2cap_server(P_INTR)
    except OSError as exc:
        print(exc, file=sys.stderr)
        print("Try: sudo systemctl restart bluetooth", file=sys.stderr)
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
