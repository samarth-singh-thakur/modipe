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
sleep 3

bluetoothctl power on
bluetoothctl pairable on
bluetoothctl discoverable on

echo "Bluetooth mouse mode is active."
echo "When this script exits, it will restore the previous Bluetooth setup."
python3 "${SCRIPT_DIR}/bluetooth_mouse.py" "$@"
