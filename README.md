# Raspberry Pi Bluetooth Mouse

This turns a Raspberry Pi into a Bluetooth mouse for an Android phone. You SSH into the Pi from your Mac, run the script, then control the Android pointer from your SSH keyboard.

## Controls

- Arrow keys: move up, down, left, right
- Space or Enter: left click
- `r`: right click
- `w` / `s`: scroll up / down
- `+` / `-`: change movement speed
- `q`: quit

## Install on the Raspberry Pi

Copy `rpi_bt_mouse.py` to the Pi, then run:

```bash
sudo apt update
sudo apt install -y python3-dbus python3-gi bluez bluez-tools
chmod +x rpi_bt_mouse.py
```

Make sure the Pi Bluetooth service is running:

```bash
sudo systemctl enable --now bluetooth
```

## Run

SSH into the Pi from your Mac and start the mouse:

```bash
sudo ./rpi_bt_mouse.py
```

On Android, open:

```text
Settings > Bluetooth > Pair new device > Raspberry Pi Mouse
```

If the phone already remembers the Pi, use "Forget" on Android first, then pair again while the script is running.

## Notes

- This uses Bluetooth Classic HID, not BLE. Android supports this as a normal mouse.
- It needs to run with `sudo` because binding Bluetooth HID L2CAP channels requires root.
- If pairing is flaky, reboot the Pi, forget the Pi on Android, and run the script again before pairing.
- On some Raspberry Pi OS images, another HID service can hold the same Bluetooth ports. Stop that service before running this script.

## Troubleshooting

If you see `UUID already registered`, BlueZ already has a HID profile active. The script now continues in that case.

If the script says `Could not bind Bluetooth L2CAP PSM 0x11`, BlueZ's `input` plugin is holding the mouse ports. Disable that plugin with a systemd override:

```bash
BTD="$(readlink -f /usr/libexec/bluetooth/bluetoothd /usr/lib/bluetooth/bluetoothd 2>/dev/null | head -n 1)"
sudo mkdir -p /etc/systemd/system/bluetooth.service.d
printf '[Service]\nExecStart=\nExecStart=%s --noplugin=input\n' "$BTD" | sudo tee /etc/systemd/system/bluetooth.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo python3 rpi_bt_mouse.py
```

Then forget the Pi in Android Bluetooth settings and pair again.

To undo this later:

```bash
sudo rm /etc/systemd/system/bluetooth.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
```
