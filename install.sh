#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/clm-1"
VERSION="1.10.0"

for required_file in clm clm_ai.py clm_flash.py clm_paths.py clm_doctor.py clm_update.py clm_firmware.ino TERMS_OF_USE.md; do
  if [[ ! -f "$SOURCE_DIR/$required_file" ]]; then
    printf 'Error: required project file is missing: %s\n' "$SOURCE_DIR/$required_file" >&2
    exit 1
  fi
done

mkdir -p "$BIN_DIR" "$DATA_DIR"
install -m 0755 "$SOURCE_DIR/clm" "$BIN_DIR/clm"
install -m 0644 "$SOURCE_DIR/clm_ai.py" "$BIN_DIR/clm_ai.py"
install -m 0644 "$SOURCE_DIR/clm_flash.py" "$BIN_DIR/clm_flash.py"
install -m 0644 "$SOURCE_DIR/clm_paths.py" "$BIN_DIR/clm_paths.py"
install -m 0644 "$SOURCE_DIR/clm_doctor.py" "$BIN_DIR/clm_doctor.py"
install -m 0644 "$SOURCE_DIR/clm_update.py" "$BIN_DIR/clm_update.py"
install -m 0644 "$SOURCE_DIR/clm_firmware.ino" "$DATA_DIR/clm_firmware.ino"
install -m 0644 "$SOURCE_DIR/README.md" "$DATA_DIR/README.md"
install -m 0644 "$SOURCE_DIR/COMMANDS.txt" "$DATA_DIR/COMMANDS.txt"
install -m 0644 "$SOURCE_DIR/CHANGELOG.md" "$DATA_DIR/CHANGELOG.md"
install -m 0644 "$SOURCE_DIR/TERMS_OF_USE.md" "$DATA_DIR/TERMS_OF_USE.md"
install -m 0644 "$SOURCE_DIR/requirements.txt" "$DATA_DIR/requirements.txt"
printf '%s\n' "$VERSION" > "$DATA_DIR/VERSION"

# Create .bashrc if this is a fresh Linux home directory.
SHELL_RC="$HOME/.bashrc"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
touch "$SHELL_RC"
if ! grep -Fqx -- "$PATH_LINE" "$SHELL_RC"; then
  printf '\n# CLM-1 command-line tool\n%s\n' "$PATH_LINE" >> "$SHELL_RC"
fi

printf '\nCLM-1 v%s installed/updated.\n' "$VERSION"
printf 'Firmware: %s/clm_firmware.ino\n' "$DATA_DIR"
printf 'Command list: %s/COMMANDS.txt\n' "$DATA_DIR"
printf 'Terms of use: %s/TERMS_OF_USE.md\n' "$DATA_DIR"
printf 'Custom macros: %s/custom_commands.json\n' "$DATA_DIR"
printf 'API key file:  ~/.config/clm-1/openai_api_key (owner-only permissions)\n'
printf '\nReload PATH in this terminal with:\n  source ~/.bashrc\n'
printf 'Or open a new terminal, then launch:\n  clm\n  clm device clm\n'
