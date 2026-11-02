#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/clm-1"

mkdir -p "$BIN_DIR" "$DATA_DIR"
install -m 0755 "$SOURCE_DIR/clm" "$BIN_DIR/clm"
install -m 0644 "$SOURCE_DIR/clm_ai.py" "$BIN_DIR/clm_ai.py"
install -m 0644 "$SOURCE_DIR/clm_firmware.ino" "$DATA_DIR/clm_firmware.ino"
install -m 0644 "$SOURCE_DIR/README.md" "$DATA_DIR/README.md"
install -m 0644 "$SOURCE_DIR/COMMANDS.txt" "$DATA_DIR/COMMANDS.txt"
install -m 0644 "$SOURCE_DIR/CHANGELOG.md" "$DATA_DIR/CHANGELOG.md"
install -m 0644 "$SOURCE_DIR/requirements.txt" "$DATA_DIR/requirements.txt"
printf '1.3.0\n' > "$DATA_DIR/VERSION"

SHELL_RC="$HOME/.bashrc"
if [[ -f "$SHELL_RC" ]] && ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC"; then
  printf '\n# CLM-1 command-line tool\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$SHELL_RC"
fi

printf '\nCLM-1 v1.3.0 installed/updated.\n'
printf 'Firmware: %s/clm_firmware.ino\n' "$DATA_DIR"
printf 'Command list: %s/COMMANDS.txt\n' "$DATA_DIR"
printf 'Custom macros: %s/custom_commands.json\n' "$DATA_DIR"
printf 'API key file:  ~/.config/clm-1/openai_api_key (owner-only permissions)\n'
printf '\nEnable the clm command in this terminal with:\n  source ~/.bashrc\n\nThen launch:\n  clm\n  clm device clm\n'
