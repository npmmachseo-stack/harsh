# BT Keyboard Appliance OS

A custom, minimal Linux OS build that boots straight into the BT Keyboard
receiver — turn a spare PC, mini-PC, or Raspberry Pi into a dedicated
appliance for this project instead of running the Windows/Linux desktop
receiver (`../desktop-receiver`) on top of a full OS.

No desktop environment, no login prompt: the machine powers on, gets an
IP over DHCP, starts listening on TCP `:9876`, and injects whatever
keystrokes the [Android sender app](../android-app) sends it into
whatever's focused on the box (e.g. a browser or media-center app you've
also installed), using the exact same JSON wire protocol as
`desktop-receiver/receiver_wifi.py`.

## Layout

```
custom-os/
├── receiver/           Linux receiver daemon (protocol-compatible with
│                        desktop-receiver/receiver_wifi.py, injects keys
│                        via /dev/uinput instead of the Windows API)
│   ├── keymap.py        pure protocol/keymap logic, unit tested
│   ├── linux_receiver.py TCP server + uinput device + main()
│   ├── test_keymap.py   unit tests (no root/hardware needed)
│   └── requirements.txt
├── buildroot/           Buildroot external tree (BR2_EXTERNAL)
│   ├── package/btkeyboard-receiver/   packages the receiver + boot script
│   ├── board/btkeyboard/rootfs-overlay/  hostname, network config
│   └── configs/btkeyboard.fragment    config layered onto a stock board defconfig
└── build.sh              downloads Buildroot and builds the image
```

## Building an image

Requires internet access and the [Buildroot host
dependencies](https://buildroot.org/downloads/manual/manual.html#requirement)
(a Linux build machine, standard build toolchain, ~5-10 GB free disk).
This was scaffolded and unit-tested in this session, but the actual
multi-GB, 30-90+ minute Buildroot compile was **not** run here — build it
yourself, and expect to iterate on `configs/btkeyboard.fragment` via
`make menuconfig` if a package name doesn't match your Buildroot version.

```sh
./build.sh x86_64        # generic PC/laptop — boots from USB, also runs in QEMU
./build.sh raspberrypi4   # Raspberry Pi 4, boots from SD card
```

Images land in `build/output-<target>/images/`. Write the disk image to
a USB stick or SD card with `dd` (or Raspberry Pi Imager / Etcher), boot
the target machine from it, and it comes up as the receiver automatically.

To test the x86_64 build without real hardware:

```sh
qemu-system-x86_64 -M pc -m 512 \
  -drive file=build/output-x86_64/images/rootfs.ext2,if=virtio,format=raw \
  -kernel build/output-x86_64/images/bzImage \
  -append "root=/dev/vda console=ttyS0" -nographic \
  -netdev user,id=n0,hostfwd=tcp::9876-:9876 -device virtio-net,netdev=n0
```

## How it works

- **Buildroot** (`buildroot/`) assembles the actual OS: a Linux kernel,
  BusyBox userland, Python 3 + `python-evdev`, and our receiver package,
  starting from Buildroot's own well-tested `qemu_x86_64_defconfig` /
  `raspberrypi4_64_defconfig` board configs so kernel/bootloader/firmware
  specifics stay upstream-maintained. Our
  [config fragment](buildroot/configs/btkeyboard.fragment) only adds what's
  specific to this appliance (hostname, network, our package).
- **`/etc/init.d/S99btkeyboard`** starts `linux_receiver.py` at boot
  (installed by the `btkeyboard-receiver` Buildroot package).
- **`receiver/linux_receiver.py`** listens on TCP `:9876` for the same
  newline-delimited JSON messages the Android app already sends
  (`{"type": "unicode"|"special"|"combo", "value": ..., "modifiers": [...]}`),
  and injects them via a virtual USB keyboard created through
  `/dev/uinput` (using `python-evdev`), instead of the Windows
  `SendInput` API the desktop receiver uses.

### A note on Unicode

Windows lets `receiver_wifi.py` type arbitrary Unicode directly
(`KEYEVENTF_UNICODE`). The Linux input layer has no equivalent — a
virtual keyboard can only send key events. So:

- ASCII text is typed as ordinary key (+ Shift) presses on a US QWERTY
  layout, which works everywhere.
- Non-ASCII text (Gujarati, Hindi, Tamil, Arabic, CJK, ...) is typed
  using the IBus/GTK "Unicode code point" method
  (`Ctrl+Shift+U <hex> Space`), which the focused app understands
  whenever an IBus-based input method is active — the common default on
  Linux desktop environments. An app with no IBus support (a bare
  framebuffer app, some kiosk browsers) won't receive non-ASCII
  characters this way; there's no lower-level fix for that on Linux.

## Running/testing the receiver without building an OS

The receiver itself can be tried on any Linux box with `/dev/uinput`
(needs the `uinput` kernel module and root, or membership of the group
that owns `/dev/uinput`):

```sh
cd receiver
pip install -r requirements.txt
sudo python3 linux_receiver.py
```

Its unit tests need neither: `python3 -m unittest discover custom-os/receiver`.
