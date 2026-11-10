#!/usr/bin/env bash
set -euo pipefail
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Library/Application Support/CLM-1"
BIN_DIR="$HOME/.local/bin"
VERSION="1.8.0"
for required_file in clm clm_ai.py clm_flash.py clm_paths.py clm_doctor.py clm_update.py clm_firmware.ino TERMS_OF_USE.md requirements.txt; do
  if [[ ! -f "$SOURCE_DIR/$required_file" ]]; then
    printf 'Error: required project file is missing: %s\n' "$required_file" >&2
    exit 1
  fi
done
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. Install Python from https://www.python.org/downloads/macos/."
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "CLM-1 requires Python 3.10 or newer."
  exit 1
fi
mkdir -p "$APP_DIR" "$BIN_DIR"
cp "$SOURCE_DIR/clm" "$SOURCE_DIR/clm_ai.py" "$SOURCE_DIR/clm_flash.py" "$SOURCE_DIR/clm_paths.py" "$SOURCE_DIR/clm_doctor.py" "$SOURCE_DIR/clm_update.py" "$APP_DIR/"
cp "$SOURCE_DIR/clm_firmware.ino" "$SOURCE_DIR/README.md" "$SOURCE_DIR/COMMANDS.txt" "$SOURCE_DIR/CHANGELOG.md" "$SOURCE_DIR/TERMS_OF_USE.md" "$SOURCE_DIR/requirements.txt" "$APP_DIR/"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then python3 -m venv "$APP_DIR/.venv"; fi
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
cat > "$BIN_DIR/clm" <<EOF
#!/bin/sh
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/clm" "\$@"
EOF
cat > "$BIN_DIR/clm_h@cker_init" <<EOF
#!/bin/sh
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/clm" clm_h@cker_init "\$@"
EOF
chmod 0755 "$BIN_DIR/clm" "$BIN_DIR/clm_h@cker_init"
for rc in "$HOME/.zprofile" "$HOME/.bash_profile"; do
  touch "$rc"
  if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$rc"; then
    printf '\n# CLM-1 command-line tools\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
  fi
done
printf '\nCLM-1 v%s installed for macOS.\n' "$VERSION"
printf 'Open a new Terminal window, or run: export PATH="$HOME/.local/bin:$PATH"\n'
printf 'Then launch: clm\nDirect firmware flasher: clm_h@cker_init\n'
printf 'Firmware and terms: %s\n' "$APP_DIR"
