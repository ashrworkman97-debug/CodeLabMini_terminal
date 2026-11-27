"""CLM-1 update checker and self-updater."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from clm_paths import APP_DIR, CONFIG_DIR

REPO = "ashrworkman97-debug/CodeLabMini_terminal"
RAW_CLI = f"https://raw.githubusercontent.com/{REPO}/main/clm"
ARCHIVE = f"https://codeload.github.com/{REPO}/zip/refs/heads/main"
CORE_FILES = ("clm", "clm_ai.py", "clm_flash.py", "clm_paths.py", "clm_doctor.py", "clm_update.py")
DATA_FILES = ("clm_firmware.ino", "README.md", "COMMANDS.txt", "CHANGELOG.md",
              "TERMS_OF_USE.md", "requirements.txt", "install.sh",
              "install_macos.sh", "install_windows.ps1")
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 512
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
ARCHIVE_READ_CHUNK_BYTES = 64 * 1024


def _latest_version(timeout: float = 2.0) -> str | None:
    """Fetch the current CLI source and extract its declared application version."""
    request = urllib.request.Request(RAW_CLI, headers={"User-Agent": "CLM-1 updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        source = response.read(2_000_000).decode("utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', source, re.M)
    return match.group(1) if match else None


def _version_tuple(value: str) -> tuple[int, ...]:
    """Convert a dotted numeric version into a tuple suitable for comparison."""
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


def _validate_source_tree(source_root: Path) -> None:
    """Reject incomplete update archives before modifying the installed application."""
    missing = [name for name in CORE_FILES if not (source_root / name).is_file()]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            "Update archive is incomplete; missing required core files: "
            f"{names}. No installed files were changed."
        )


def _extract_archive_safely(archive: zipfile.ZipFile, destination: Path) -> None:
    """Extract a ZIP into a temporary directory with path and size limits."""
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise RuntimeError("Update archive contains too many entries; refusing to install it.")

    declared_size = 0
    for member in members:
        if member.file_size < 0:
            raise RuntimeError("Update archive contains an invalid file size.")
        declared_size += member.file_size
        if declared_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise RuntimeError(
                "Update archive expands beyond the 64 MiB safety limit; refusing to install it."
            )

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    seen_paths = set()
    actual_size = 0

    for member in members:
        name = member.filename
        if not name or "\x00" in name or "\\" in name:
            raise RuntimeError("Unsafe path found in update archive.")
        posix_path = PurePosixPath(name)
        windows_path = PureWindowsPath(name)
        parts = posix_path.parts
        if (not parts or posix_path.is_absolute() or windows_path.is_absolute()
                or windows_path.drive or ".." in parts
                or any(":" in part for part in parts)):
            raise RuntimeError("Unsafe path found in update archive.")

        relative_name = "/".join(parts).casefold()
        if relative_name in seen_paths:
            raise RuntimeError(f"Duplicate path found in update archive: {name}")
        seen_paths.add(relative_name)

        mode = member.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise RuntimeError(f"Unsupported special file in update archive: {name}")

        target = root.joinpath(*parts)
        if member.is_dir() or kind == stat.S_IFDIR:
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        member_size = 0
        with archive.open(member) as source, target.open("xb") as output:
            while True:
                chunk = source.read(ARCHIVE_READ_CHUNK_BYTES)
                if not chunk:
                    break
                member_size += len(chunk)
                actual_size += len(chunk)
                if actual_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise RuntimeError(
                        "Update archive expands beyond the 64 MiB safety limit; refusing to install it."
                    )
                output.write(chunk)

        if member_size != member.file_size:
            raise RuntimeError(f"Update archive entry size did not match its metadata: {name}")



def _replace_files_transactionally(files: list[tuple[Path, Path]]) -> None:
    """Stage all files, then replace them with best-effort rollback on failure."""
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    preserve_backups = False

    try:
        # Prepare every replacement beside its destination first. A staging
        # failure therefore cannot leave a mixture of old and new modules.
        for source, destination in files:
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, staged_name = tempfile.mkstemp(
                prefix=f".{destination.name}.clm-update-",
                dir=destination.parent,
            )
            os.close(descriptor)
            staged_path = Path(staged_name)
            try:
                shutil.copy2(source, staged_path)
            except Exception:
                staged_path.unlink(missing_ok=True)
                raise
            staged.append((staged_path, destination))

        try:
            for staged_path, destination in staged:
                if destination.exists() or destination.is_symlink():
                    descriptor, backup_name = tempfile.mkstemp(
                        prefix=f".{destination.name}.clm-backup-",
                        dir=destination.parent,
                    )
                    os.close(descriptor)
                    backup_path = Path(backup_name)
                    backup_path.unlink()
                    os.replace(destination, backup_path)
                    backups.append((backup_path, destination))

                os.replace(staged_path, destination)
                installed.append(destination)
        except Exception as install_error:
            rollback_errors = []
            for destination in reversed(installed):
                try:
                    destination.unlink(missing_ok=True)
                except OSError as exc:
                    rollback_errors.append(f"could not remove {destination}: {exc}")
            for backup_path, destination in reversed(backups):
                if backup_path.exists() or backup_path.is_symlink():
                    try:
                        os.replace(backup_path, destination)
                    except OSError as exc:
                        rollback_errors.append(
                            f"could not restore {destination} from {backup_path}: {exc}"
                        )
            if rollback_errors:
                preserve_backups = True
                raise RuntimeError(
                    "Update replacement failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from install_error
            raise
    finally:
        for staged_path, _destination in staged:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        if not preserve_backups:
            for backup_path, _destination in backups:
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    pass

def install_update() -> int:
    """Download the latest source archive and replace the installed CLM-1 files."""
    print("[update] Checking GitHub and downloading the latest CLM-1...")
    try:
        request = urllib.request.Request(ARCHIVE, headers={"User-Agent": "CLM-1 updater"})
        with urllib.request.urlopen(request, timeout=30) as response:
            archive_data = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(archive_data) > MAX_ARCHIVE_BYTES:
            raise RuntimeError("Update archive is unexpectedly large; refusing to install it.")
        with tempfile.TemporaryDirectory(prefix="clm-update-") as temp:
            archive_path = Path(temp) / "source.zip"
            archive_path.write_bytes(archive_data)
            with zipfile.ZipFile(archive_path) as archive:
                root = Path(temp) / "source"
                root.mkdir()
                _extract_archive_safely(archive, root)
            entries = list(root.iterdir())
            if len(entries) != 1 or not entries[0].is_dir():
                raise RuntimeError(
                    "Update archive has an unexpected layout; expected one top-level source directory."
                )
            source_root = entries[0]
            _validate_source_tree(source_root)
            code_dir = Path(__file__).resolve().parent
            app_dir = Path(APP_DIR)
            install_files = []
            for name in CORE_FILES:
                source = source_root / name
                if source.is_file():
                    install_files.append((source, code_dir / name))
            for name in DATA_FILES:
                source = source_root / name
                if source.is_file():
                    install_files.append((source, app_dir / name))
            version_match = re.search(
                r'^APP_VERSION\\s*=\\s*["\\']([^"\\']+)["\\']',
                (source_root / "clm").read_text(encoding="utf-8"), re.M)
            if version_match:
                version_source = Path(temp) / "VERSION"
                version_source.write_text(version_match.group(1) + "\\n", encoding="utf-8")
                install_files.append((version_source, app_dir / "VERSION"))
            _replace_files_transactionally(install_files)
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
