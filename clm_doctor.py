"""Offline setup diagnostics for CLM-1."""
from __future__ import annotations

from dataclasses import dataclass
import shutil
import sys


USB_VID = 0x0403
USB_PID = 0x6015


@dataclass(frozen=True)
class Diagnostic:
    status: str
    name: str
    detail: str


def _load_serial():
    import serial
    from serial.tools import list_ports
    return serial, list_ports


def _find_firmware():
    from clm_flash import find_firmware
    return find_firmware()


def collect_diagnostics() -> list[Diagnostic]:
    """Inspect the local CLM-1 setup without contacting or changing the Mini."""
    checks: list[Diagnostic] = []

    if sys.version_info >= (3, 10):
        checks.append(Diagnostic("OK", "Python", sys.version.split()[0]))
    else:
        checks.append(Diagnostic(
            "FAIL", "Python",
            f"{sys.version.split()[0]} found; CLM-1 requires Python 3.10 or newer.",
        ))

    try:
        serial, list_ports = _load_serial()
    except ImportError:
        checks.append(Diagnostic(
            "FAIL", "pySerial",
            "Not installed. Install it with: python -m pip install pyserial.",
        ))
    else:
        checks.append(Diagnostic(
            "OK", "pySerial", f"Version {getattr(serial, '__version__', 'unknown')} is available."
        ))
        try:
            ports = list(list_ports.comports())
        except Exception as exc:
            checks.append(Diagnostic("WARN", "USB ports", f"Could not enumerate serial ports: {exc}"))
        else:
            minis = [
                port for port in ports
                if getattr(port, "vid", None) == USB_VID
                and getattr(port, "pid", None) == USB_PID
            ]
            if minis:
                names = ", ".join(str(getattr(port, "device", "unknown")) for port in minis)
                checks.append(Diagnostic(
                    "OK", "Code Lab Mini",
                    f"Found {len(minis)} FTDI 0403:6015 device(s): {names}.",
                ))
            elif ports:
                visible = ", ".join(str(getattr(port, "device", "unknown")) for port in ports)
                checks.append(Diagnostic(
                    "WARN", "Code Lab Mini",
                    "No FTDI 0403:6015 device found. Visible serial ports: "
                    f"{visible}. Check the USB cable and ChromeOS/Linux USB sharing.",
                ))
            else:
                checks.append(Diagnostic(
                    "WARN", "Code Lab Mini",
                    "No serial ports found. Plug in the Mini and, on ChromeOS, share it with Linux.",
                ))

    cli = shutil.which("arduino-cli")
    if cli:
        checks.append(Diagnostic("OK", "Arduino CLI", f"Found at {cli}."))
    else:
        checks.append(Diagnostic(
            "INFO", "Arduino CLI",
            "Not found on PATH. Optional; needed only for clm_h@cker_init firmware flashing.",
        ))

    try:
        firmware = _find_firmware()
    except (FileNotFoundError, OSError) as exc:
        checks.append(Diagnostic("WARN", "Firmware sketch", str(exc)))
    else:
        checks.append(Diagnostic("OK", "Firmware sketch", f"Found at {firmware}."))

    return checks


def run_doctor(stream=None) -> int:
    """Print a readable diagnostic report and return nonzero for required failures."""
    output = stream or sys.stdout
    checks = collect_diagnostics()
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}", file=output)

    counts = {
        status: sum(check.status == status for check in checks)
        for status in ("OK", "WARN", "INFO", "FAIL")
    }
    print(
        "\nSummary: "
        f"{counts['OK']} OK, {counts['WARN']} warning(s), "
        f"{counts['INFO']} optional, {counts['FAIL']} failure(s).",
        file=output,
    )
    return 1 if counts["FAIL"] else 0
