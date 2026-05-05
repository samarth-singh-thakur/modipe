#!/usr/bin/env python3
"""
Configure a Raspberry Pi as a USB HID mouse gadget and send mouse reports.

Run on the Raspberry Pi as root:
    sudo python3 rpi_usb_mouse_gadget.py setup
    sudo python3 rpi_usb_mouse_gadget.py demo

This requires a Raspberry Pi model/port that supports USB OTG/device mode
and a USB data cable connected from the Pi's USB gadget port to the phone.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


GADGET_ROOT = Path("/sys/kernel/config/usb_gadget")
GADGET = GADGET_ROOT / "rpi_mouse"
HID_DEV = Path("/dev/hidg0")


MOUSE_REPORT_DESC = bytes(
    [
        0x05,
        0x01,  # Usage Page (Generic Desktop)
        0x09,
        0x02,  # Usage (Mouse)
        0xA1,
        0x01,  # Collection (Application)
        0x09,
        0x01,  #   Usage (Pointer)
        0xA1,
        0x00,  #   Collection (Physical)
        0x05,
        0x09,  #     Usage Page (Buttons)
        0x19,
        0x01,  #     Usage Minimum (1)
        0x29,
        0x03,  #     Usage Maximum (3)
        0x15,
        0x00,  #     Logical Minimum (0)
        0x25,
        0x01,  #     Logical Maximum (1)
        0x95,
        0x03,  #     Report Count (3)
        0x75,
        0x01,  #     Report Size (1)
        0x81,
        0x02,  #     Input (Data, Variable, Absolute)
        0x95,
        0x01,  #     Report Count (1)
        0x75,
        0x05,  #     Report Size (5)
        0x81,
        0x03,  #     Input (Constant)
        0x05,
        0x01,  #     Usage Page (Generic Desktop)
        0x09,
        0x30,  #     Usage (X)
        0x09,
        0x31,  #     Usage (Y)
        0x09,
        0x38,  #     Usage (Wheel)
        0x15,
        0x81,  #     Logical Minimum (-127)
        0x25,
        0x7F,  #     Logical Maximum (127)
        0x75,
        0x08,  #     Report Size (8)
        0x95,
        0x03,  #     Report Count (3)
        0x81,
        0x06,  #     Input (Data, Variable, Relative)
        0xC0,  #   End Collection
        0xC0,  # End Collection
    ]
)


def require_root() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run this script as root, for example with sudo.")


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="ascii")


def write_bytes(path: Path, value: bytes) -> None:
    path.write_bytes(value)


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_modules() -> None:
    os.system("modprobe libcomposite")


def get_udc_name() -> str:
    udcs = sorted(Path("/sys/class/udc").iterdir())
    if not udcs:
        raise SystemExit(
            "No USB Device Controller found. Check that USB OTG/device mode is enabled "
            "and that you are using a Pi USB port that supports gadget mode."
        )
    return udcs[0].name


def setup_gadget() -> None:
    require_root()
    load_modules()

    if not GADGET_ROOT.exists():
        raise SystemExit(
            "/sys/kernel/config/usb_gadget does not exist. Mount configfs first:\n"
            "    sudo mount -t configfs none /sys/kernel/config"
        )

    mkdir(GADGET)
    write_text(GADGET / "idVendor", "0x1d6b")  # Linux Foundation
    write_text(GADGET / "idProduct", "0x0104")  # Multifunction Composite Gadget
    write_text(GADGET / "bcdDevice", "0x0100")
    write_text(GADGET / "bcdUSB", "0x0200")

    strings = GADGET / "strings/0x409"
    mkdir(strings)
    write_text(strings / "serialnumber", "00000001")
    write_text(strings / "manufacturer", "Raspberry Pi")
    write_text(strings / "product", "Pi USB Mouse")

    config = GADGET / "configs/c.1"
    mkdir(config)
    config_strings = config / "strings/0x409"
    mkdir(config_strings)
    write_text(config_strings / "configuration", "HID Mouse")
    write_text(config / "MaxPower", "100")

    hid = GADGET / "functions/hid.usb0"
    mkdir(hid)
    write_text(hid / "protocol", "2")  # Mouse
    write_text(hid / "subclass", "1")  # Boot interface
    write_text(hid / "report_length", "4")
    write_bytes(hid / "report_desc", MOUSE_REPORT_DESC)

    link = config / "hid.usb0"
    if not link.exists():
        link.symlink_to(hid)

    write_text(GADGET / "UDC", get_udc_name())
    print("USB mouse gadget is active. Android should detect a mouse now.")


def cleanup_gadget() -> None:
    require_root()
    if not GADGET.exists():
        return

    try:
        write_text(GADGET / "UDC", "")
    except OSError:
        pass

    link = GADGET / "configs/c.1/hid.usb0"
    if link.exists() or link.is_symlink():
        link.unlink()

    for path in [
        GADGET / "functions/hid.usb0",
        GADGET / "configs/c.1/strings/0x409",
        GADGET / "configs/c.1",
        GADGET / "strings/0x409",
        GADGET,
    ]:
        try:
            path.rmdir()
        except OSError:
            pass


def clamp_i8(value: int) -> int:
    return max(-127, min(127, value))


def send_report(buttons: int = 0, x: int = 0, y: int = 0, wheel: int = 0) -> None:
    report = bytes(
        [
            buttons & 0x07,
            clamp_i8(x) & 0xFF,
            clamp_i8(y) & 0xFF,
            clamp_i8(wheel) & 0xFF,
        ]
    )
    with HID_DEV.open("wb", buffering=0) as hid:
        hid.write(report)


def click(button: int = 1) -> None:
    send_report(buttons=button)
    time.sleep(0.05)
    send_report()


def demo() -> None:
    require_root()
    if not HID_DEV.exists():
        raise SystemExit(f"{HID_DEV} does not exist. Run setup first.")

    print("Moving pointer in a small square, then left-clicking.")
    for dx, dy in [(40, 0), (0, 40), (-40, 0), (0, -40)]:
        for _ in range(8):
            send_report(x=dx // 8, y=dy // 8)
            time.sleep(0.02)
    click()
    print("Demo complete.")


def move(x: int, y: int, wheel: int) -> None:
    require_root()
    send_report(x=x, y=y, wheel=wheel)


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi USB HID mouse gadget")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Configure and enable the USB mouse gadget")
    subparsers.add_parser("cleanup", help="Disable and remove the USB mouse gadget")
    subparsers.add_parser("demo", help="Move the mouse pointer and click once")

    move_parser = subparsers.add_parser("move", help="Send one relative mouse movement")
    move_parser.add_argument("--x", type=int, default=0, help="Relative X movement, -127..127")
    move_parser.add_argument("--y", type=int, default=0, help="Relative Y movement, -127..127")
    move_parser.add_argument("--wheel", type=int, default=0, help="Relative wheel movement")

    click_parser = subparsers.add_parser("click", help="Send one mouse click")
    click_parser.add_argument(
        "--button",
        type=int,
        default=1,
        choices=[1, 2, 4],
        help="1=left, 2=right, 4=middle",
    )

    args = parser.parse_args()
    if args.command == "setup":
        setup_gadget()
    elif args.command == "cleanup":
        cleanup_gadget()
    elif args.command == "demo":
        demo()
    elif args.command == "move":
        move(args.x, args.y, args.wheel)
    elif args.command == "click":
        require_root()
        click(args.button)


if __name__ == "__main__":
    main()
