"""CLM-1 update checker and self-updater."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from clm_paths import APP_DIR, CONFIG_DIR

REPO = "ashrworkman97-debug/CodeLabMini_terminal"
RAW_CLI = f"https://raw.githubusercontent.com/{REPO}/main/clm"
ARCHIVE = f"https://codeload.github.com/{REPO}/zip/refs/heads/main"
CORE_FILES = ("clm", "clm_ai.py", "clm_flash.py", "clm_paths.py", "clm_update.py")
DATA_FILES = ("clm_firmware.ino", "README.md", "COMMANDS.txt", "CHANGELOG.md",
              "TERMS_OF_USE.md", "requirements.txt", "install.sh",
              "install_macos.sh", "install_windows.ps1")


def _latest_version(timeout: float = 2.0) -> str | None:
    request = urllib.request.Request(RAW_CLI, headers={"User-Agent": "CLM-1 updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        source = response.read(2_000_000).decode("utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', source, re.M)
    return match.group(1) if match else None


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return (0,)


def check_for_update(current_version: str, *, silent: bool = False,
                     force: bool = False) -> bool:
    """Return True when a newer version is available; cache successful checks for 24h."""
    cache = CONFIG_DIR / "update-check.json"
    try:
        if not force and cache.exists():
            state = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - float(state.get("checked_at", 0)) < 86400:
                latest = str(state.get("latest", current_version))
                if _version_tuple(latest) > _version_tuple(current_version):
                    print(f"[update] CLM-1 {latest} is available (you have {current_version}). Run `clm update`.")
                    return True
                return False
        latest = _latest_version()
        if not latest:
            return False
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked_at": time.time(), "latest": latest}), encoding="utf-8")
        if _version_tuple(latest) > _version_tuple(current_version):
            print(f"[update] CLM-1 {latest} is available (you have {current_version}). Run `clm update`.")
            return True
        if not silent:
            print(f"[update] You're up to date (CLM-1 {current_version}).")
        return False
    except Exception as exc:
        if not silent:
            print(f"[update] Could not check GitHub right now: {exc}")
        return False


def install_update() -> int:
    """Download the latest source archive and replace the installed CLM-1 files."""
    print("[update] Checking GitHub and downloading the latest CLM-1...")
    try:
        request = urllib.request.Request(ARCHIVE, headers={"User-Agent": "CLM-1 updater"})
        with urllib.request.urlopen(request, timeout=30) as response:
            archive_data = response.read(20 * 1024 * 1024 + 1)
        if len(archive_data) > 20 * 1024 * 1024:
            raise RuntimeError("Update archive is unexpectedly large; refusing to install it.")
        with tempfile.TemporaryDirectory(prefix="clm-update-") as temp:
            archive_path = Path(temp) / "source.zip"
            archive_path.write_bytes(archive_data)
            with zipfile.ZipFile(archive_path) as archive:
                root = Path(temp) / "source"
                root.mkdir()
                for member in archive.infolist():
                    target = (root / member.filename).resolve()
                    if root.resolve() not in target.parents and target != root.resolve():
                        raise RuntimeError("Unsafe path found in update archive.")
                archive.extractall(root)
            source_root = next(root.iterdir())
            code_dir = Path(__file__).resolve().parent
            app_dir = Path(APP_DIR)
            app_dir.mkdir(parents=True, exist_ok=True)
            for name in CORE_FILES:
                source = source_root / name
                if source.is_file():
                    shutil.copy2(source, code_dir / name)
            for name in DATA_FILES:
                source = source_root / name
                if source.is_file():
                    shutil.copy2(source, app_dir / name)
            version_match = re.search(
                r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']',
                (source_root / "clm").read_text(encoding="utf-8"), re.M)
            if version_match:
                (app_dir / "VERSION").write_text(version_match.group(1) + "\n", encoding="utf-8")
        try:
            (CONFIG_DIR / "update-check.json").unlink()
        except FileNotFoundError:
            pass
        print("[update] CLM-1 updated successfully! Close and reopen CLM-1 to load the new version.")
        return 0
    except Exception as exc:
        print(f"[update] Update failed: {exc}")
        print("Your existing CLM-1 installation has been left in place where possible.")
        return 1
