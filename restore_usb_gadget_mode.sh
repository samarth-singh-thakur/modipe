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
CONFIG_BACKUP="${BACKUP_DIR}/$(basename "${CONFIG_FILE}").bak"
CMDLINE_BACKUP="${BACKUP_DIR}/cmdline.txt.bak"

if [[ -f "${CONFIG_BACKUP}" && -f "${CMDLINE_BACKUP}" ]]; then
  cp "${CONFIG_BACKUP}" "${CONFIG_FILE}"
  cp "${CMDLINE_BACKUP}" "${CMDLINE_FILE}"
  echo "Restored boot files from ${BACKUP_DIR}"
else
  echo "Backup files not found. Removing gadget-mode settings directly."
  sed -i.bak '/^[[:space:]]*# Enable USB OTG gadget mode[[:space:]]*$/d' "${CONFIG_FILE}"
  sed -i.bak '/^[[:space:]]*dtoverlay=dwc2[[:space:]]*$/d' "${CONFIG_FILE}"
  tmp_file="$(mktemp)"
  sed 's/[[:space:]]modules-load=dwc2//g; s/modules-load=dwc2[[:space:]]//g; s/^modules-load=dwc2$//' "${CMDLINE_FILE}" > "${tmp_file}"
  cat "${tmp_file}" > "${CMDLINE_FILE}"
  rm -f "${tmp_file}"
fi

echo "USB gadget boot settings restored."
echo "Rebooting now..."
reboot
