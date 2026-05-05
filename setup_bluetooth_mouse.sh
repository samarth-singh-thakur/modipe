#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

apt-get update
apt-get install -y bluez rfkill python3-dbus python3-gi

retry_bluetoothctl() {
  local description="$1"
  shift

  for attempt in 1 2 3 4 5; do
    if bluetoothctl "$@"; then
      return 0
    fi

    echo "Bluetooth is busy while trying to ${description}; retrying (${attempt}/5)..."
    sleep 2
  done

  echo "Could not ${description}. Check: systemctl status bluetooth"
  return 1
}

systemctl daemon-reload
systemctl enable bluetooth
systemctl restart bluetooth
rfkill unblock bluetooth || true
sleep 3

retry_bluetoothctl "power on the adapter" power on
retry_bluetoothctl "make the adapter pairable" pairable on
retry_bluetoothctl "make the adapter discoverable" discoverable on

echo "Bluetooth HID dependencies installed."
echo "Now run: sudo ./run_bluetooth_mouse_safe.sh"
