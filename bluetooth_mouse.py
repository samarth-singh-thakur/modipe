#!/usr/bin/env python3
"""
Bluetooth HID mouse for Raspberry Pi 3B.

Run on the Pi:
    sudo python3 bluetooth_mouse.py

Then pair from Android while this script is running. After Android connects,
the script sends a small mouse movement demo.
"""

from __future__ import annotations

import argparse
import os
import socket
import time
from pathlib import Path

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib


HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
PROFILE_PATH = "/bluez/rpi_hid_mouse_profile"


REPORT_DESCRIPTOR_HEX = (
    "05010902a10185010901a10005091901290315002501950375018102950175058103"
    "05010930093109381581257f750895038106c0c0"
)


SDP_RECORD = f"""
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
      <sequence>
        <uuid value="0x0011" />
        <uint16 value="0x0013" />
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
          <uint16 value="0x0013" />
        </sequence>
        <sequence>
          <uuid value="0x0011" />
        </sequence>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0100">
    <text value="Raspberry Pi Bluetooth Mouse" />
  </attribute>
  <attribute id="0x0101">
    <text value="Bluetooth HID mouse" />
  </attribute>
  <attribute id="0x0102">
    <text value="Raspberry Pi" />
  </attribute>
  <attribute id="0x0200">
    <uint16 value="0x0100" />
  </attribute>
  <attribute id="0x0201">
    <uint16 value="0x0111" />
  </attribute>
  <attribute id="0x0202">
    <uint8 value="0x80" />
  </attribute>
  <attribute id="0x0203">
    <uint8 value="0x00" />
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
        <text encoding="hex" value="{REPORT_DESCRIPTOR_HEX}" />
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
  <attribute id="0x020b">
    <boolean value="false" />
  </attribute>
  <attribute id="0x020c">
    <boolean value="false" />
  </attribute>
  <attribute id="0x020d">
    <boolean value="true" />
  </attribute>
  <attribute id="0x020e">
    <uint16 value="0x0640" />
  </attribute>
  <attribute id="0x020f">
    <boolean value="true" />
  </attribute>
  <attribute id="0x0210">
    <boolean value="true" />
  </attribute>
</record>
"""


class BluetoothMouse:
    def __init__(self, interrupt_socket: socket.socket) -> None:
        self.interrupt_socket = interrupt_socket

    def send_report(self, buttons: int = 0, x: int = 0, y: int = 0, wheel: int = 0) -> None:
        report = bytes(
            [
                0xA1,  # HIDP data input report
                0x01,  # Report ID 1
                buttons & 0x07,
                clamp_i8(x) & 0xFF,
                clamp_i8(y) & 0xFF,
                clamp_i8(wheel) & 0xFF,
            ]
        )
        self.interrupt_socket.send(report)

    def click(self, button: int = 1) -> None:
        self.send_report(buttons=button)
        time.sleep(0.05)
        self.send_report()

    def demo(self) -> None:
        print("Moving pointer in a small square, then left-clicking.")
        for dx, dy in [(40, 0), (0, 40), (-40, 0), (0, -40)]:
            for _ in range(8):
                self.send_report(x=dx // 8, y=dy // 8)
                time.sleep(0.02)
        self.click()


class HidProfile(dbus.service.Object):
    def __init__(self, bus: dbus.SystemBus, run_demo: bool) -> None:
        super().__init__(bus, PROFILE_PATH)
        self.run_demo = run_demo
        self.connections: list[socket.socket] = []

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self) -> None:
        print("Bluetooth profile released")

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device: dbus.ObjectPath, fd: dbus.types.UnixFd, properties: dict) -> None:
        print(f"BlueZ reported a new connection from {device}")
        connection = socket.socket(fileno=fd.take())
        self.connections.append(connection)

        if len(self.connections) == 1:
            print("Control channel connected")
        elif len(self.connections) == 2:
            print("Interrupt channel connected")
            mouse = BluetoothMouse(self.connections[1])
            if self.run_demo:
                GLib.idle_add(self._run_demo, mouse)
            print("Connected. Press Ctrl+C to stop.")

    def _run_demo(self, mouse: BluetoothMouse) -> bool:
        mouse.demo()
        return False

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device: dbus.ObjectPath) -> None:
        print(f"BlueZ requested disconnection from {device}")
        for connection in self.connections:
            connection.close()
        self.connections.clear()

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def Cancel(self, device: dbus.ObjectPath) -> None:
        print(f"Bluetooth connection canceled for {device}")


def require_root() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run as root: sudo python3 bluetooth_mouse.py")


def run_command(command: str) -> None:
    os.system(command)


def prepare_adapter(name: str) -> None:
    run_command("hciconfig hci0 up")
    run_command(f"hciconfig hci0 name '{name}'")
    run_command("hciconfig hci0 class 0x002580")
    run_command("bluetoothctl power on >/dev/null")
    run_command("bluetoothctl agent NoInputNoOutput >/dev/null")
    run_command("bluetoothctl default-agent >/dev/null")
    run_command("bluetoothctl pairable on >/dev/null")
    run_command("bluetoothctl discoverable on >/dev/null")


def register_profile(run_demo: bool) -> HidProfile:
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    profile = HidProfile(bus, run_demo)
    manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
    options = {
        "ServiceRecord": SDP_RECORD,
        "Role": "server",
        "RequireAuthentication": False,
        "RequireAuthorization": False,
        "AutoConnect": True,
    }
    manager.RegisterProfile(PROFILE_PATH, HID_UUID, options)
    return profile


def clamp_i8(value: int) -> int:
    return max(-127, min(127, value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi Bluetooth HID mouse")
    parser.add_argument("--name", default="RaspberryPi Mouse", help="Bluetooth device name")
    parser.add_argument("--no-demo", action="store_true", help="Wait for a connection but do not move the pointer")
    args = parser.parse_args()

    require_root()
    if not Path("/usr/bin/bluetoothctl").exists():
        raise SystemExit("bluetoothctl not found. Install BlueZ: sudo apt install bluez")

    prepare_adapter(args.name)
    profile = register_profile(run_demo=not args.no_demo)
    loop = GLib.MainLoop()

    try:
        print("Waiting for Android to connect...")
        print(f"On Android, pair with: {args.name}")
        loop.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        for connection in profile.connections:
            connection.close()


if __name__ == "__main__":
    main()
