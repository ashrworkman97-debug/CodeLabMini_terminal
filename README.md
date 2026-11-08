# CLM-1 — Code Lab Mini Command Line Manager

[![CI](https://github.com/ashrworkman97-debug/CodeLabMini_terminal/actions/workflows/ci.yml/badge.svg)](https://github.com/ashrworkman97-debug/CodeLabMini_terminal/actions/workflows/ci.yml)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

CLM-1 is an open-source command-line toolkit for the **Let's Start Coding Code Lab Mini**. It replaces the usual browser-only workflow with a local Python terminal, custom device firmware, hardware effects, and an optional AI-powered command builder.

> **Project status:** Experimental / hobby project. Hardware behavior depends on the Code Lab Mini revision and the firmware installed on it. Back up anything important before changing firmware.

## At a glance

- Control the red, green, and blue LEDs independently or together.
- Play tones, melodies, Morse code, and sound effects.
- Control the vibration motor and read the buttons and analog knob.
- Run built-in light shows, alerts, games, and terminal utilities.
- Optionally generate reusable hardware macros through the OpenAI API.
- Check GitHub for CLM-1 updates automatically at startup, with a one-command self-updater.
- Run a read-only setup diagnosis with `clm doctor` before troubleshooting USB or firmware flashing.
- Use the project on Windows 10/11, macOS, Linux, and ChromeOS Linux.

## Contents

- [Requirements](#requirements)
- [Hardware map](#hardware-map)
- [Install CLM-1](#install-clm-1)
- [Windows and macOS](#windows-and-macos)
- [Install firmware](#install-or-update-the-mini-firmware-without-the-browser-editor)
- [Connect on ChromeOS](#connect-from-chromeos)
- [Quick start](#quick-start)
- [Command groups](#command-groups)
- [AI Command Studio](#ai-command-studio-optional)
- [Run tests](#run-tests)
- [Troubleshooting](#troubleshooting)
- [Security](#security-and-privacy)
- [Contributing](#contributing)
- [Terms of use](TERMS_OF_USE.md)
- [License](#license)

## Requirements

- A Code Lab Mini and a USB data cable.
- Windows 10/11, macOS, Linux, or ChromeOS with the Linux development environment enabled.
- Python 3.10 or newer.
- `pyserial` 3.5 or newer.
- Permission to access the USB serial device.
- Arduino CLI for direct firmware flashing (optional for normal terminal control).

On Debian, Ubuntu, or ChromeOS Linux, install the runtime dependency with:

```bash
sudo apt update
sudo apt install python3 python3-serial
```

On other Linux distributions, install the `pyserial` dependency using the distribution's package manager or a Python virtual environment.

## Hardware map

The included firmware targets the ATmega328P-compatible Code Lab Mini and uses ordinary Arduino functions. It does **not** require the proprietary `LetsStartCoding.h` library.

| Function | Firmware pin |
|---|---:|
| Speaker | D2 |
| Vibration motor (PWM) | D3 |
| Arcade buttons A, B, LEFT, RIGHT | D4–D7 |
| Red LED (LED 1) | D8 |
| Green LED (LED 2) | D10 |
| Blue LED (LED 3) | D12 |
| Turn knob | A0 |

The LEDs are discrete on/off outputs, not full-spectrum RGB channels. Color names such as yellow, cyan, magenta, and white are combinations of the three LEDs.

The firmware communicates over USB serial at **9600 baud** using newline-terminated ASCII commands.

## Install CLM-1

First, install **Python 3.10 or newer**. Then clone the repository:

```bash
git clone https://github.com/ashrworkman97-debug/CodeLabMini_terminal.git
cd CodeLabMini_terminal
```

### Linux and ChromeOS

On Debian, Ubuntu, or ChromeOS Linux, install the serial dependency and run the user-level installer:

```bash
sudo apt update
sudo apt install python3 python3-serial
bash install.sh
source ~/.bashrc
```

Launch the console with `clm`, or connect immediately with `clm device clm`. CLM-1 quietly checks GitHub for a newer host version at startup (at most once per day). If one is available, run `clm update` to download and install it, then close and reopen CLM-1. Use `clm update check` to check manually. This updates the host software; firmware updates still require `clm_h@cker_init`.

### Windows and macOS

#### Windows 10/11

Open PowerShell in the cloned repository folder. If needed, install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/) and enable the Python launcher (`py`). Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1
```

The installer creates an isolated Python environment, installs pyserial, and adds per-user `clm` and `clm_h@cker_init` commands. Open a **new** PowerShell or Windows Terminal window after installation, then run:

```powershell
clm
clm scan
clm connect COM3
```

Use the COM port shown by `clm scan`; it may not be COM3. No administrator access is required. If Windows does not expose the Mini as a serial port, install the appropriate FTDI VCP driver from [FTDI](https://ftdichip.com/drivers/).

#### macOS

Install Python 3.10+ from [python.org](https://www.python.org/downloads/macos/) if it is not already available. In Terminal, clone the repository and run:

```bash
bash install_macos.sh
```

The installer creates an isolated Python environment and adds `clm` and `clm_h@cker_init` to `~/.local/bin`. Open a new Terminal window (or run `export PATH="$HOME/.local/bin:$PATH"`) and launch:

```bash
clm
clm scan
clm connect /dev/cu.usbserial-XXXX
```

The serial device name varies; use the exact path reported by `clm scan`. macOS may require an FTDI VCP driver depending on the operating-system version and USB interface.

## Install or update the Mini firmware without the browser editor

The host application and controller firmware are separate. Updating CLM-1 on the Chromebook does **not** automatically update the firmware on the Mini.

CLM-1 includes `clm_h@cker_init`, a local Arduino CLI flasher. It compiles the bundled sketch and uploads the resulting HEX directly through the Mini's USB-to-serial bootloader. It does not open the manufacturer's website or browser editor, burn a new bootloader, or change chip fuses.

Install [Arduino CLI](https://arduino.github.io/arduino-cli/latest/installation/) once and make sure `arduino-cli` is on your PATH. The first run can offer to download/install the Arduino AVR platform if it is missing.

Inside CLM-1, connect the Mini and run:

```text
CLM-1> clm_h@cker_init
```

The command automatically selects a single FTDI device with VID:PID `0403:6015`. It compiles first, shows the exact port and board profile, and only uploads after you type `FLASH`. If more than one Mini is connected, select one explicitly:

```text
CLM-1> clm_h@cker_init --port /dev/ttyUSB0
```

To check that the firmware compiles without changing any device:

```text
CLM-1> clm_h@cker_init --compile-only
```

The default board profile is `arduino:avr:uno`, based on the manufacturer's description of the ATmega328P as similar to the Arduino Uno. This assumes an Uno-compatible 16 MHz serial bootloader; the public product specifications do not identify every bootloader detail or hardware revision. Confirm that your Mini uses compatible bootloader settings before authorizing an upload. Use `--fqbn` only when you know the correct alternative profile. The command never attempts to burn or repair a bootloader.

The installer copies the sketch to `~/.local/share/clm-1/clm_firmware.ino` and the uploader module alongside the CLM-1 application.

## Connect from ChromeOS

1. Connect the Code Lab Mini by USB.
2. In ChromeOS, open **Settings → Developers → Linux development environment → USB preferences** (wording may vary).
3. Share the Mini's USB serial interface with Linux.
4. Close the manufacturer's browser editor or any serial monitor that has the port open.
5. Start CLM-1 with `clm device clm`.

If automatic detection does not work, run `scan` inside CLM-1 to list serial ports. Then reconnect using the device path shown by the scan, for example:

```text
CLM-1> scan
CLM-1> reconnect
```

You can also connect to an explicit port from the Linux terminal:

```bash
clm connect /dev/ttyUSB0
```

The USB bridge commonly identifies as FTDI **VID:PID 0403:6015**. The Linux device path may differ from one system to another.

## Quick start

Before connecting, run the read-only setup check from your terminal:

```bash
clm doctor
```

It checks Python, pySerial, visible USB serial ports, the optional Arduino CLI, and the bundled firmware sketch. It does not contact or change the Mini.

Once connected, try these commands inside the CLM-1 prompt:

```text
ping
info
status
led 1 on
led 2 on
led 3 on
led all off
color magenta
rainbow 2 90
beep 700 300
motor 160 500
morse HELLO WORLD
demo
help
```

Leave the console with `quit` or `exit`.

## Command groups

Use `help` inside CLM-1 for the built-in help. The full reference is in [COMMANDS.txt](COMMANDS.txt).

**Connection and device:** `help`, `version`, `update`, `doctor`, `device`, `scan`, `ping`, `info`, `status`, `buttons`, `stream`, `reconnect`, `echo`, `reset`, `panic`, `quit`.

**LEDs and effects:** `led`, `color`, `rgb`, `blink`, `chase`, `wave`, `rainbow`, `ledtest`.

**Speaker and vibration:** `beep`, `tone`, `stop`, `motor`, `buzz`, `pulse`, `morse`, `sos`, `melody`, `metro`.

**Built-in shows:** `party`, `siren`, `alarm`, `laser`, `powerup`, `explosion`, `heartbeat`, `countdown`, `demo`, `glitch`, `beacon`, `portal`, `fireworks`, `hyperspace`, `dice`, `coin`, `random`.

**Knob modes:** `knob tone`, `knob motor`, `knob color`, and `knob off`.

**Local terminal utilities:** `roll`, `rps`, `magic8`, `joke`, `fortune`, `time`, `uptime`, `whoami`, `ascii`, `clear`, and `credits`.

## AI Command Studio (optional)

CLM-1 can use the OpenAI API to generate custom hardware macros from plain-language descriptions. For example:

```text
ai setup
ai test
ai status
ai create make a blue light show with three short beeps
custom list
custom show COMMAND_NAME
custom run COMMAND_NAME
custom remove COMMAND_NAME
ai forget
```

AI features require an **OpenAI API key**. API usage is billed separately from a ChatGPT subscription.

Generated commands are declarative action data, not executable Python or shell code. The validator restricts actions to supported LED, color, beep, motor, wait, and blink operations, applies parameter and duration limits, and asks for confirmation before saving.

The API key is stored locally in the operating system's per-user CLM-1 configuration directory (Linux: `~/.config/clm-1/`; macOS: `~/Library/Application Support/CLM-1/Config/`; Windows: `%APPDATA%\\CLM-1\\`). CLM-1 restricts file permissions where the operating system supports them. You can also provide `OPENAI_API_KEY` through the environment. Never commit API keys, settings, or personal custom-command files to Git.

## Run tests

The offline test suite does not need a connected Mini or an OpenAI API key:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile clm clm_ai.py clm_flash.py clm_paths.py clm_doctor.py
python3 clm doctor
bash -n install.sh install_macos.sh
python3 clm --version
python3 clm --help
```

GitHub Actions runs the Python checks on Linux, Windows, and macOS with Python 3.10, 3.11, 3.12, and 3.13. Firmware compilation runs on Linux. Firmware compilation and physical-device behavior still need to be checked with a compatible Arduino toolchain and real hardware.

## Troubleshooting

### CLM-1 cannot find the Mini

- Confirm that the USB cable supports data, not just charging.
- Share the USB device with Linux in ChromeOS settings.
- Run `scan` inside CLM-1 and check the listed serial ports.
- Close the manufacturer's editor and other serial-monitor applications.

### USB I/O error / errno 5

Linux may have lost access to the USB serial device. Unplug and reconnect the Mini, share it with Linux again, close other serial applications, and reconnect in CLM-1.

### `ERR UNKNOWN COMMAND`

The firmware on the Mini may be older than the host application. Upload the repository's `clm_firmware.ino`, then reconnect. Updating the Python application alone does not update the controller.

### The AI command builder does not work

- Run `ai status` and `ai test`.
- Confirm that the API key is valid and that the selected model is available to your API account.
- Check that API billing and usage limits allow requests.
- Remember that a ChatGPT subscription does not include API credits.

## Security and privacy

- Never publish your API key or paste it into an issue.
- The AI macro builder sends the command description and generation request to the OpenAI API when you use it.
- Generated macros are validated and limited to supported hardware actions. This is a safety boundary, not a guarantee that every hardware effect is harmless in every physical setup.
- Keep local configuration and generated custom commands out of version control.

See [SECURITY.md](SECURITY.md) for reporting security issues.

## Contributing

Bug reports, hardware compatibility notes, documentation improvements, and tested command ideas are welcome. Please include your CLM-1 version, firmware version, operating system, and the exact command/error when reporting a problem. **Never include API keys or other secrets.**

See [CONTRIBUTING.md](CONTRIBUTING.md) and the GitHub pull request template before submitting a change.

## License

CLM-1 is distributed under the **Mozilla Public License 2.0**. See [LICENSE](LICENSE) for the complete license text. Review [TERMS_OF_USE.md](TERMS_OF_USE.md) for the hardware-risk terms before flashing.

---

Made for experimenting with the Code Lab Mini. Have fun, and keep building!
