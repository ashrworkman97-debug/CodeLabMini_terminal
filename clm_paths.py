"""Platform-aware per-user storage locations for CLM-1."""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Mapping, Optional

def get_app_dir(home: Optional[Path] = None, system: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> Path:
    home = Path(home or Path.home())
    system = system or sys.platform
    env = env or os.environ
    if system == "win32":
        return Path(env.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "CLM-1"
    if system == "darwin":
        return home / "Library" / "Application Support" / "CLM-1"
    return home / ".local" / "share" / "clm-1"

def get_config_dir(home: Optional[Path] = None, system: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> Path:
    home = Path(home or Path.home())
    system = system or sys.platform
    env = env or os.environ
    if system == "win32":
        return Path(env.get("APPDATA", str(home / "AppData" / "Roaming"))) / "CLM-1"
    if system == "darwin":
        return home / "Library" / "Application Support" / "CLM-1" / "Config"
    return home / ".config" / "clm-1"

APP_DIR = get_app_dir()
CONFIG_DIR = get_config_dir()
