"""Offline setup diagnostics for CLM-1."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
import sys


USB_VID = 0x0403
USB_PID = 0x6015


@dataclass(frozen=True)
class Diagnostic:
    """One setup-check result with a severity, label, and explanatory detail."""

    status: str
    name: str
    detail: str


def _load_serial():
    """Import pySerial lazily so diagnostics can report a missing dependency."""
    import serial
    from serial.tools import list_ports
    return serial, list_ports


def _find_firmware():
    """Locate the bundled firmware sketch using the installer's shared logic."""
    from clm_flash import find_firmware
    return find_firmware()


def _check_usb_permissions(ports: list[object]) -> Diagnostic:
    """Check read/write access to detected Unix serial-device nodes without opening them."""
    if sys.platform.startswith("win"):
        return Diagnostic(
            "INFO", "USB permissions",
            "Windows manages COM-port access through its device handles; this check is not applicable.",
        )

    inaccessible = [
        str(getattr(port, "device", "unknown"))
        for port in ports
        if not os.access(str(getattr(port, "device", "")), os.R_OK | os.W_OK)
    ]
    if inaccessible:
        devices = ", ".join(inaccessible)
        if sys.platform.startswith("linux"):
            detail = (
                f"No read/write access to {devices}. On many Debian-based systems, "
                "add your account to the dialout group with "
                'sudo usermod -aG dialout "$USER", then sign out and back in.'
            )
        else:
            detail = (
                f"No read/write access to {devices}. Check the device-node permissions "
                "and close other serial-monitor applications."
            )
        return Diagnostic("WARN", "USB permissions", detail)

    return Diagnostic(
        "OK", "USB permissions",
        "Read/write access is available for the detected Code Lab Mini serial device(s).",
    )


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
                if len(minis) > 1:
                    checks.append(Diagnostic(
                        "WARN", "Code Lab Mini",
                        f"Found {len(minis)} FTDI 0403:6015 devices: {names}. "
                        "Firmware flashing needs an explicit target; use "
                        "`clm_h@cker_init --port PORT`.",
                    ))
                else:
                    checks.append(Diagnostic(
                        "OK", "Code Lab Mini",
                        f"Found one FTDI 0403:6015 device: {names}.",
                    ))
                checks.append(_check_usb_permissions(minis))
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


def run_doctor(stream=None, *, json_output: bool = False, strict: bool = False) -> int:
    """Print a human-readable or machine-readable report and return its exit code."""
    output = stream if stream is not None else sys.stdout
    checks = collect_diagnostics()
    summary = {
        status.lower(): sum(check.status == status for check in checks)
        for status in ("OK", "WARN", "INFO", "FAIL")
    }
    exit_code = 1 if summary["fail"] or (strict and summary["warn"]) else 0

    if json_output:
        report = {
            "schema_version": 1,
            "checks": [
                {"status": check.status, "name": check.name, "detail": check.detail}
                for check in checks
            ],
            "summary": summary,
            "strict": strict,
            "exit_code": exit_code,
        }
        print(json.dumps(report, indent=2), file=output)
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}", file=output)
        print(
            "\nSummary: "
            f"{summary['ok']} OK, {summary['warn']} warning(s), "
            f"{summary['info']} optional, {summary['fail']} failure(s).",
            file=output,
        )
        if strict:
            print("Strict mode: warnings cause a non-zero exit code.", file=output)
    return exit_code
