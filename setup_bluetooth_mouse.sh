#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

apt-get update
apt-get install -y bluez python3-dbus python3-gi

if [[ -x /usr/lib/bluetooth/bluetoothd ]]; then
  BLUETOOTHD="/usr/lib/bluetooth/bluetoothd"
elif [[ -x /usr/libexec/bluetooth/bluetoothd ]]; then
  BLUETOOTHD="/usr/libexec/bluetooth/bluetoothd"
else
  BLUETOOTHD="bluetoothd"
fi

mkdir -p /etc/systemd/system/bluetooth.service.d
cat >/etc/systemd/system/bluetooth.service.d/hid-device.conf <<EOF
[Service]
ExecStart=
ExecStart=${BLUETOOTHD} --compat -P input
EOF

systemctl daemon-reload
systemctl enable bluetooth
systemctl restart bluetooth

bluetoothctl power on
bluetoothctl pairable on
bluetoothctl discoverable on

echo "Bluetooth HID dependencies installed."
echo "Now run: sudo python3 bluetooth_mouse.py"
