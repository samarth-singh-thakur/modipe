#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DROPIN_DIR="/etc/systemd/system/bluetooth.service.d"
MODIPE_DROPIN="${DROPIN_DIR}/zzz-modipe-hid-device.conf"
OLD_MODIPE_DROPIN="${DROPIN_DIR}/hid-device.conf"
BRIDGE_SERVICE="bt-call-bridge.service"

if [[ -x /usr/lib/bluetooth/bluetoothd ]]; then
  BLUETOOTHD="/usr/lib/bluetooth/bluetoothd"
elif [[ -x /usr/libexec/bluetooth/bluetoothd ]]; then
  BLUETOOTHD="/usr/libexec/bluetooth/bluetoothd"
else
  BLUETOOTHD="bluetoothd"
fi

BRIDGE_WAS_ACTIVE="no"
BRIDGE_WAS_ENABLED="no"

retry_bluetoothctl() {
  local description="$1"
  shift

  for attempt in 1 2 3 4 5; do
    if bluetoothctl "$@"; then
      return 0
    fi

    echo "Bluetooth failed while trying to ${description}; resetting adapter and retrying (${attempt}/5)..."
    rfkill unblock bluetooth 2>/dev/null || true
    hciconfig hci0 reset 2>/dev/null || true
    sleep 3
  done

  echo "Could not ${description}. Try: sudo systemctl restart bluetooth && sudo hciconfig hci0 reset"
  return 1
}

if systemctl list-unit-files "${BRIDGE_SERVICE}" >/dev/null 2>&1; then
  if systemctl is-active --quiet "${BRIDGE_SERVICE}"; then
    BRIDGE_WAS_ACTIVE="yes"
  fi
  if systemctl is-enabled --quiet "${BRIDGE_SERVICE}" 2>/dev/null; then
    BRIDGE_WAS_ENABLED="yes"
  fi
fi

restore_previous_bluetooth() {
  echo
  echo "Restoring previous Bluetooth setup..."

  rm -f "${MODIPE_DROPIN}"
  rm -f "${OLD_MODIPE_DROPIN}"
  systemctl daemon-reload
  systemctl restart bluetooth || true

  if [[ "${BRIDGE_WAS_ENABLED}" == "yes" ]]; then
    systemctl enable "${BRIDGE_SERVICE}" >/dev/null 2>&1 || true
  fi

  if [[ "${BRIDGE_WAS_ACTIVE}" == "yes" ]]; then
    systemctl start "${BRIDGE_SERVICE}" >/dev/null 2>&1 || true
  fi

  echo "Restore complete."
}

trap restore_previous_bluetooth EXIT INT TERM

mkdir -p "${DROPIN_DIR}"
cat >"${MODIPE_DROPIN}" <<EOF
[Service]
ExecStart=
ExecStart=${BLUETOOTHD} --experimental --compat -P input
EOF

rm -f "${OLD_MODIPE_DROPIN}"
systemctl stop "${BRIDGE_SERVICE}" 2>/dev/null || true
systemctl daemon-reload
systemctl restart bluetooth
rfkill unblock bluetooth 2>/dev/null || true
hciconfig hci0 reset 2>/dev/null || true
sleep 5

retry_bluetoothctl "power on the adapter" power on
retry_bluetoothctl "keep the adapter pairable" pairable-timeout 0
retry_bluetoothctl "make the adapter pairable" pairable on
retry_bluetoothctl "keep the adapter discoverable" discoverable-timeout 0
retry_bluetoothctl "make the adapter discoverable" discoverable on

echo "Bluetooth mouse mode is active."
echo "When this script exits, it will restore the previous Bluetooth setup."
python3 "${SCRIPT_DIR}/bluetooth_mouse.py" "$@"
