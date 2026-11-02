# CLM-1 — Code Lab Mini Command Line Manager

CLM-1 is an open-source command-line toolkit for the **Let's Start Coding Code Lab Mini**. It replaces the usual browser-only workflow with a local Python terminal, custom device firmware, hardware effects, and an optional AI-powered command builder.

> **Project status:** Experimental / hobby project. Hardware behavior depends on the Code Lab Mini revision and the firmware installed on it. Back up anything important before changing firmware.

## What it does

- Controls the Mini's red, green, and blue LEDs independently or together.
- Plays tones, melodies, Morse code, and sound effects through the onboard speaker.
- Controls the vibration motor, including timed vibration and pulses.
- Reads the four arcade buttons and analog knob; can stream input changes to the terminal.
- Includes built-in light shows, alarms, games, and terminal utilities.
- Optionally asks the OpenAI API to generate safe, reusable hardware macros.
- Runs on Linux, including the Linux environment on ChromeOS.

## Hardware

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

The firmware communicates over USB serial at **9600 baud** using newline-terminated ASCII commands.

## Repository contents

| File | Purpose |
|---|---|
| `clm` | Main CLM-1 command-line application |
| `clm_ai.py` | Optional AI command builder and safe macro runner |
| `clm_firmware.ino` | Firmware for the Code Lab Mini |
| `install.sh` | Linux user-level installer |
| `requirements.txt` | Python dependencies |
| `COMMANDS.txt` | Command reference |
| `CHANGELOG.md` | Release history |

## Requirements

- A Code Lab Mini with USB cable.
- Linux, or ChromeOS with the Linux development environment enabled.
- Python 3.10 or newer recommended.
- `pyserial`.
- Permission to access the USB serial device.
- An Arduino-compatible compile/upload workflow for installing firmware.

On Debian/Ubuntu/ChromeOS Linux, install the serial dependency with:

```bash
sudo apt update
sudo apt install python3 python3-serial
```

## Install CLM-1

Download the repository ZIP from GitHub and extract it, or clone it:

```bash
git clone https://github.com/ashrworkman97-debug/CodeLabMini_terminal.git
cd CodeLabMini_terminal
```

Run the installer:

```bash
bash install.sh
source ~/.bashrc
```

The installer places the command-line application in `~/.local/bin` and adds that directory to PATH in `~/.bashrc`. Because `bash install.sh` runs the installer in a separate process, that PATH change does not automatically update the terminal you already have open. Run `source ~/.bashrc` to reload the updated PATH in your current terminal (or simply open a new terminal). If `clm` is still not found, check that `~/.local/bin` is in your PATH.

## Install the Mini firmware

1. Open `clm_firmware.ino` in an Arduino-compatible editor.
2. Select the board/profile and serial port appropriate for your Code Lab Mini.
3. Compile and upload the sketch.
4. Close the upload tool's serial monitor before starting CLM-1; only one application can normally own the serial port at a time.

The firmware is separate from the Linux application. Updating CLM-1 on the Chromebook does **not** automatically update the firmware on the Mini.

## Connect from ChromeOS

1. Connect the Code Lab Mini by USB.
2. In ChromeOS, open **Settings → Developers → Linux development environment → USB preferences** (wording may vary).
3. Share the Mini's USB serial interface with Linux.
4. Close the manufacturer's browser editor or serial monitor if it has the port open.
5. Start CLM-1:

```bash
clm device clm
```

If automatic detection does not work, scan for serial ports:

```text
CLM-1> scan
```

Then reconnect using the device path shown by the scan (for example, `/dev/ttyUSB0`):

```bash
clm connect /dev/ttyUSB0
```

The USB bridge commonly identifies as FTDI **VID:PID 0403:6015**. Your device path may differ.

## Quick start

Once connected, try:

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

To leave CLM-1, enter `quit` or `exit`.

## Command groups

Use `help` inside CLM-1 for the full built-in help. The separate [COMMANDS.txt](COMMANDS.txt) file is easier to read or print.

### Connection and device

`help`, `version`, `device`, `scan`, `ping`, `info`, `status`, `buttons`, `stream on|off`, `reconnect`, `echo TEXT`, `reset`, `panic`, `quit`.

### LEDs and effects

`led 1|2|3 on|off|toggle`, `led all on|off`, `led clear`, `color NAME`, `rgb R G B`, `blink`, `chase`, `wave`, `rainbow`, `ledtest`.

The three LEDs are discrete on/off outputs. Color names such as yellow, cyan, magenta, and white mean combinations of those three LEDs; they are not full-spectrum RGB mixing.

### Speaker and vibration

`beep`, `tone`, `stop`, `motor`, `buzz`, `pulse`, `morse`, `sos`, `melody`, `metro`.

### Built-in shows

`party`, `siren`, `alarm`, `laser`, `powerup`, `explosion`, `heartbeat`, `countdown`, `demo`, `glitch`, `beacon`, `portal`, `fireworks`, `hyperspace`, `dice`, `coin`, `random`.

### Knob modes

`knob tone`, `knob motor`, `knob color`, and `knob off`.

### Terminal utilities

`roll`, `rps`, `magic8`, `joke`, `fortune`, `time`, `uptime`, `whoami`, `ascii`, `clear`, and `credits`.

## AI Command Studio (optional)

CLM-1 can use the OpenAI API to generate custom hardware macros from plain-language descriptions. For example, you can ask it to create a command that flashes the LEDs, plays a short tone sequence, and vibrates the motor.

AI features require an **OpenAI API key** and API usage is billed separately from a ChatGPT subscription.

Inside CLM-1:

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

Generated commands are stored as declarative action data, not executable Python or shell code. The macro validator restricts actions to supported LED, color, beep, motor, wait, and blink operations, applies parameter limits, and requires confirmation before saving.

The API key is stored locally under `~/.config/clm-1/` with owner-only file permissions. Do not commit API keys, settings, or personal custom-command files to Git.

## Troubleshooting

### CLM-1 cannot find the Mini

- Check that the USB cable supports data, not just charging.
- Share the USB device with Linux in ChromeOS settings.
- Run `scan` and look for the serial device.
- Check that the manufacturer editor or another serial monitor is closed.

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
- The AI macro builder sends the command description and macro-generation request to the OpenAI API.
- Generated macros are validated and limited to the supported hardware actions; they cannot run arbitrary shell commands or Python.
- Keep local configuration and generated custom commands out of version control.

See [SECURITY.md](SECURITY.md) for reporting security issues.

## Contributing

Bug reports, hardware compatibility notes, documentation improvements, and tested command ideas are welcome. Please include your CLM-1 version, firmware version, operating system, and the exact command/error when reporting a problem. **Never include API keys or other secrets.**

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

CLM-1 is distributed under the **Mozilla Public License 2.0**. See [LICENSE](LICENSE) for the full license text.

---

Made for experimenting with the Code Lab Mini. Have fun, and keep building!
