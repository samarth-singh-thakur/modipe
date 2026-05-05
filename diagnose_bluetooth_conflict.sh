#!/usr/bin/env bash
set -euo pipefail

echo "== Bluetooth service =="
systemctl --no-pager --full status bluetooth || true

echo
echo "== Bluetooth-related system services =="
systemctl list-units --type=service --all --no-pager | grep -Ei 'blue|bt|hid|tyrion|talk|mouse|keyboard' || true

echo
echo "== Bluetooth/HID processes =="
ps -eo pid,user,args | grep -Ei 'bluetooth_mouse|TyrionTalk|tyrion|blue|bt|hid|mouse|keyboard' | grep -v grep || true

echo
echo "== User services =="
systemctl --user list-units --type=service --all --no-pager 2>/dev/null | grep -Ei 'blue|bt|hid|tyrion|talk|mouse|keyboard' || true

echo
echo "== Paired/trusted Bluetooth devices =="
bluetoothctl devices || true

echo
echo "If TyrionTalk appears above, stop/disable it before running bluetooth_mouse.py."
