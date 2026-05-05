# Raspberry Pi USB Mouse Gadget

Python helper script to make a USB OTG-capable Raspberry Pi enumerate as a USB HID mouse when connected to an Android phone.

## Raspberry Pi setup

Enable USB gadget mode on the Pi, then reboot:

```bash
sudo ./enable_usb_gadget_mode.sh
```

To restore the original boot settings later:

```bash
sudo ./restore_usb_gadget_mode.sh
```

The enable script makes a backup in `/boot/usb-gadget-backup` before changing boot files.

Manual setup, if you prefer to edit the files yourself:

Add this to `/boot/config.txt` or `/boot/firmware/config.txt`:

```txt
dtoverlay=dwc2
```

Add this to `/boot/cmdline.txt` after `rootwait`, keeping the file as one single line:

```txt
modules-load=dwc2
```

## Usage

Run as root on the Raspberry Pi:

```bash
sudo python3 rpi_usb_mouse_gadget.py setup
sudo python3 rpi_usb_mouse_gadget.py demo
```

Move or click manually:

```bash
sudo python3 rpi_usb_mouse_gadget.py move --x 20 --y 0
sudo python3 rpi_usb_mouse_gadget.py click
```

Disable the gadget:

```bash
sudo python3 rpi_usb_mouse_gadget.py cleanup
```

## Notes

Use a Raspberry Pi USB port that supports OTG/device mode and a real USB data cable. Charge-only cables will not work.
