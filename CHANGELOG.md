# Changelog

Notable changes to CLM-1 are documented here.

## 1.4.0 — Direct Firmware Flashing

- Added `clm_h@cker_init` for local Arduino CLI compilation and USB-serial firmware uploads.
- Added FTDI 0403:6015 detection, explicit port selection, compile-only mode, and typed FLASH confirmation.
- Added prompt-based installation of the required Arduino platform core.
- Added offline uploader tests and project Terms of Use.
- Updated the host application, installer, and command documentation to 1.4.0.

## 1.5.0 — Windows and macOS Support

- Added native per-user PowerShell installer for Windows 10/11.
- Added macOS installer with an isolated Python environment and shell launchers.
- Added platform-aware application/configuration storage paths.
- Updated serial-port examples and explicit-port handling for COM ports and macOS device paths.
- Made API-key file writing compatible with Windows.
- Expanded CI and tests to cover Linux, Windows, and macOS.

## 1.6.0 — Power-up and Self-Updater

- Reworked POWERUP into a longer charging sequence with escalating pitch, LED cycling, vibration crescendo, and a final burst.
- Added a quiet automatic GitHub update check at startup and a `clm update` self-updater.
- Added `clm update check` for a manual version check.

## 1.7.0 — Setup Diagnostics

- Added `clm doctor`, a read-only diagnostic report for Python, pySerial, USB serial visibility, Arduino CLI, and the bundled firmware sketch; `--json` provides a versioned report for scripts.
- Added offline tests for connected, disconnected, and incomplete local setups.
- Added the diagnostic module to Linux, Windows, macOS, and self-updater installs.

## 1.8.0 — USB Access Diagnostics

- Extended `clm doctor` to check read/write permissions for detected Unix serial devices without opening the port.
- Added Linux dialout-group guidance when a detected device is not accessible.
- Marked the filesystem permission check as not applicable on Windows COM ports.
- Added offline tests for accessible, inaccessible, and Windows serial-device behavior.

## 1.9.0 — Strict Diagnostic Mode

- Added `clm doctor --strict` (also available inside the interactive console) to return a non-zero exit code when warnings or required failures are reported.
- Added a `strict` field to JSON diagnostic reports and offline tests for strict text, JSON, and CLI behavior.
- Updated Linux, macOS, and Windows installer version labels to 1.9.0.

## 1.10.0 — Multi-device Diagnostics

- Updated `clm doctor` to warn when multiple matching FTDI 0403:6015 devices are visible, since firmware flashing requires an explicit target when more than one Mini is connected.
- Included the detected port names in the warning and recommended `clm_h@cker_init --port PORT` for explicit selection.
- Added an offline regression test for multiple matching devices.
- Updated the CLI, Linux/macOS/Windows installer labels, and command reference to 1.10.0.

## Unreleased

- Added offline unit tests for the AI macro validator.
- Added GitHub Actions CI for supported Python versions, Python compilation, installer syntax, and CLI startup.
- Added secret/configuration exclusions, a security policy, and GitHub issue/PR templates.
- Improved the installer so a missing `~/.bashrc` is created before adding the CLM-1 PATH entry.
- Refreshed project documentation and contributor guidance.

## 1.3.0 — AI Command Studio and Mini Firmware

- Added optional OpenAI API integration for generating custom hardware macros.
- Added hidden API-key entry, local key storage, model selection, connection testing, and key removal.
- Added schema-validated macro generation with preview and explicit save confirmation.
- Added custom command listing, inspection, execution, and deletion.
- Updated the Code Lab Mini firmware protocol to version 1.3.0.
- Added support for the `VIBRATE` serial command alias.
- Documented installation, hardware connections, command usage, and troubleshooting.

## 1.2.1

- Refined the built-in command set and terminal help.
- Updated host and firmware version reporting.

## 1.2.0

- Added individual LED controls and color combinations.
- Added LED animations including blink, chase, wave, and rainbow.
- Added speaker, vibration motor, knob-control, and status commands.
- Added hardware effects and local terminal utilities.
- Added reset behavior for device outputs when leaving the application.
