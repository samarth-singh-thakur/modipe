#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

CONFIG_FILE=""
if [[ -f /boot/firmware/config.txt ]]; then
  CONFIG_FILE="/boot/firmware/config.txt"
elif [[ -f /boot/config.txt ]]; then
  CONFIG_FILE="/boot/config.txt"
else
  echo "Could not find /boot/firmware/config.txt or /boot/config.txt"
  exit 1
fi

CMDLINE_FILE="/boot/cmdline.txt"
BACKUP_DIR="/boot/usb-gadget-backup"

if [[ ! -f "${CMDLINE_FILE}" ]]; then
  echo "Could not find ${CMDLINE_FILE}"
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

CONFIG_BACKUP="${BACKUP_DIR}/$(basename "${CONFIG_FILE}").bak"
CMDLINE_BACKUP="${BACKUP_DIR}/cmdline.txt.bak"

if [[ ! -f "${CONFIG_BACKUP}" ]]; then
  cp "${CONFIG_FILE}" "${CONFIG_BACKUP}"
fi

if [[ ! -f "${CMDLINE_BACKUP}" ]]; then
  cp "${CMDLINE_FILE}" "${CMDLINE_BACKUP}"
fi

if ! grep -qE '^[[:space:]]*dtoverlay=dwc2([[:space:]]|$)' "${CONFIG_FILE}"; then
  printf '\n# Enable USB OTG gadget mode\n%s\n' 'dtoverlay=dwc2' >> "${CONFIG_FILE}"
fi

if ! grep -qw 'modules-load=dwc2' "${CMDLINE_FILE}"; then
  tmp_file="$(mktemp)"
  sed 's/rootwait/rootwait modules-load=dwc2/' "${CMDLINE_FILE}" > "${tmp_file}"
  cat "${tmp_file}" > "${CMDLINE_FILE}"
  rm -f "${tmp_file}"
fi

echo "USB gadget boot settings enabled."
echo "Backups saved in ${BACKUP_DIR}"
echo "Rebooting now..."
reboot
