# Raspberry Pi 3B Bluetooth Mouse

Bluetooth HID mouse script for Raspberry Pi 3 Model B. This is the correct approach for Pi 3B because its USB ports cannot act as a USB mouse device.

## Install

Run on the Raspberry Pi:

```bash
sudo ./setup_bluetooth_mouse.sh
```

## Run

Start the Bluetooth mouse service:

```bash
sudo ./run_bluetooth_mouse_safe.sh
```

The safe runner temporarily stops TyrionTalk's `bt-call-bridge`, switches BlueZ into HID mouse mode, runs the mouse script, and restores the previous Bluetooth setup when you press Ctrl+C.

Run without the movement demo:

```bash
sudo ./run_bluetooth_mouse_safe.sh --no-demo
```

On Android, open Bluetooth settings and pair with:

```txt
RaspberryPi Mouse
```

After Android connects, the Pi sends a small mouse movement demo and one click.

## Useful Commands

Make the Pi discoverable again:

```bash
bluetoothctl discoverable on
bluetoothctl pairable on
```

Remove an old Android pairing and pair again:

```bash
bluetoothctl devices
bluetoothctl remove PHONE_MAC_ADDRESS
```

Find another project/service that is using Bluetooth HID:

```bash
./diagnose_bluetooth_conflict.sh
```

## Notes

This is for Raspberry Pi 3B Bluetooth HID. The older USB gadget scripts in this repo are only useful for boards with a usable USB OTG/device port, such as Pi Zero or Pi Zero 2 W.
