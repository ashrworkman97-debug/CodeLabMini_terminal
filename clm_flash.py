"""Direct Arduino CLI uploader for CLM-1 firmware."""
from __future__ import annotations
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from clm_paths import APP_DIR

USB_VID = 0x0403
USB_PID = 0x6015
DEFAULT_FQBN = "arduino:avr:uno"
CLI_INSTALL_URL = "https://arduino.github.io/arduino-cli/latest/installation/"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="clm_h@cker_init",
        description="Compile and upload the CLM-1 firmware directly over USB serial.",
    )
    parser.add_argument("--port", help="serial port for the Code Lab Mini")
    parser.add_argument("--fqbn", default=DEFAULT_FQBN, help="Arduino board profile")
    parser.add_argument("--compile-only", action="store_true", help="compile but do not upload")
    return parser


def find_firmware(search_dirs: Optional[Iterable[Path]] = None) -> Path:
    if search_dirs is None:
        search_dirs = (
            Path(__file__).resolve().parent,
            APP_DIR,
        )
    for directory in search_dirs:
        candidate = Path(directory) / "clm_firmware.ino"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("clm_firmware.ino not found. Re-clone the repository or rerun the platform installer.")


def select_port(ports: Iterable[object], requested: Optional[str] = None):
    available = list(ports)
    if requested:
        for port in available:
            if getattr(port, "device", None) == requested:
                identified = (
                    getattr(port, "vid", None) == USB_VID
                    and getattr(port, "pid", None) == USB_PID
                )
                return port, identified
        raise RuntimeError(f"Port {requested!r} is not visible to Linux. Check USB sharing.")
    matches = [
        port for port in available
        if getattr(port, "vid", None) == USB_VID and getattr(port, "pid", None) == USB_PID
    ]
    if len(matches) == 1:
        return matches[0], True
    if len(matches) > 1:
        names = ", ".join(str(getattr(p, "device", "?")) for p in matches)
        raise RuntimeError(f"Multiple Code Lab Mini devices found ({names}); use --port PORT.")
    raise RuntimeError(
        "No Code Lab Mini with FTDI VID:PID 0403:6015 found. Plug it in, share it with Linux, "
        "close other serial apps, or choose a visible port with --port."
    )


def _list_ports():
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("Install pyserial with: python -m pip install pyserial") from exc
    return list(list_ports.comports())


def _run(command: list[str], timeout: int = 600) -> bool:
    print("\n[flash] $ " + " ".join(str(part) for part in command))
    try:
        result = subprocess.run(command, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[flash] Command timed out after {timeout} seconds.", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"[flash] Could not start command: {exc}", file=sys.stderr)
        return False
    if result.returncode:
        print(f"[flash] Command failed with exit code {result.returncode}.", file=sys.stderr)
        return False
    return True


def _installed_platforms(cli: str) -> set[str]:
    try:
        result = subprocess.run(
            [cli, "core", "list"], check=False, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not query Arduino CLI platforms: {exc}") from exc
    if result.returncode:
        details = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"arduino-cli core list failed: {details}")
    found = set()
    for line in result.stdout.splitlines():
        cols = line.split()
        if cols and cols[0].count(":") == 1:
            found.add(cols[0])
    return found


def _ensure_platform(cli: str, platform: str) -> bool:
    if platform in _installed_platforms(cli):
        return True
    print(f"[flash] Arduino platform {platform} is not installed.")
    try:
        answer = input(f"Download and install {platform} now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[flash] Cancelled.")
        return False
    if answer not in ("y", "yes"):
        print("[flash] Platform installation declined. No firmware was uploaded.")
        return False
    return _run([cli, "core", "update-index"]) and _run([cli, "core", "install", platform])


def _confirm(port: str, identified: bool, fqbn: str, firmware: Path) -> bool:
    print("\n" + "=" * 60)
    print("CLM-1 FIRMWARE UPLOAD — CONFIRMATION REQUIRED")
    print("=" * 60)
    print(f"Firmware : {firmware}")
    print(f"Port     : {port}")
    print(f"Board    : {fqbn}")
    if not identified:
        print("WARNING  : The manually selected port's FTDI ID was not verified.")
    if fqbn == DEFAULT_FQBN:
        print("Profile  : Arduino Uno (16 MHz, standard Uno serial bootloader settings)")
    print("The existing sketch on this board will be overwritten.")
    print("This command does not burn/replace the bootloader or change chip fuses.")
    try:
        answer = input("Type FLASH to authorize this upload, or anything else to cancel: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[flash] Cancelled.")
        return False
    return answer == "FLASH"


def handle_flash_command(args: list[str], default_port: Optional[str] = None):
    try:
        options = build_parser().parse_args(args)
    except SystemExit as exc:
        return int(exc.code or 0), None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{5,160}", options.fqbn):
        print("[flash] Invalid FQBN; expected a value such as arduino:avr:uno.", file=sys.stderr)
        return 2, None
    cli = shutil.which("arduino-cli")
    if not cli:
        print("[flash] Arduino CLI is not installed or not on PATH.", file=sys.stderr)
        print(f"Install it from {CLI_INSTALL_URL}", file=sys.stderr)
        return 2, None
    try:
        firmware = find_firmware()
    except FileNotFoundError as exc:
        print(f"[flash] {exc}", file=sys.stderr)
        return 2, None

    port_name = None
    try:
        if not options.compile_only:
            port, identified = select_port(_list_ports(), options.port or default_port)
            port_name = str(port.device)
        parts = options.fqbn.split(":")
        if len(parts) < 3:
            raise RuntimeError("FQBN must include package, architecture, and board.")
        if not _ensure_platform(cli, ":".join(parts[:2])):
            return 1, port_name

        with tempfile.TemporaryDirectory(prefix="clm1-flash-") as tmp:
            root = Path(tmp)
            sketch_dir = root / "clm_firmware"
            build_dir = root / "build"
            sketch_dir.mkdir()
            build_dir.mkdir()
            shutil.copyfile(firmware, sketch_dir / "clm_firmware.ino")
            compile_args = [
                cli, "compile", "--fqbn", options.fqbn, "--warnings", "all",
                "--output-dir", str(build_dir), str(sketch_dir),
            ]
            if not _run(compile_args):
                print("[flash] Compilation failed; the connected board was not changed.")
                return 1, port_name
            if options.compile_only:
                print("[flash] Compile successful. No hardware was changed.")
                return 0, None

            hex_files = [
                p for p in build_dir.glob("*.hex")
                if not p.name.endswith(".with_bootloader.hex")
            ]
            if len(hex_files) != 1:
                print(f"[flash] Expected one application HEX file, found {len(hex_files)}.", file=sys.stderr)
                return 1, port_name
            if not _confirm(port_name, identified, options.fqbn, firmware):
                print("[flash] No firmware was uploaded.")
                return 1, port_name

            upload_args = [
                cli, "upload", "--fqbn", options.fqbn, "--port", port_name,
                "--input-file", str(hex_files[0]), "--verify",
            ]
            if not _run(upload_args):
                print("[flash] Upload failed. Check board profile, bootloader, USB sharing, and port ownership.")
                return 1, port_name
            print("\n[flash] Upload and flash verification completed successfully.")
            return 0, port_name
    except (RuntimeError, OSError) as exc:
        print(f"[flash] {exc}", file=sys.stderr)
        return 1, port_name
