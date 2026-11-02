#!/usr/bin/env python3
"""AI-assisted, validated custom macros for CLM-1.

Generated macros are declarative data only. They never execute Python, shell,
Arduino code, or arbitrary serial strings.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".local" / "share" / "clm-1"
CONFIG_DIR = Path.home() / ".config" / "clm-1"
COMMANDS_FILE = APP_DIR / "custom_commands.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
KEY_FILE = CONFIG_DIR / "openai_api_key"
API_URL = "https://api.openai.com/v1/responses"
MODELS_URL = "https://api.openai.com/v1/models"
DEFAULT_MODEL = "gpt-6-luna"
MAX_STEPS = 30
MAX_TOTAL_MS = 20_000

COLORS = {"OFF", "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "MAGENTA", "WHITE"}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,23}$")
MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{2,100}$")

# Strict structured-output schema. All fields are present; unused fields are null.
STEP_PROPERTIES = {
    "action": {"type": "string", "enum": ["led", "color", "beep", "motor", "wait", "blink"]},
    "led": {"type": ["integer", "null"], "enum": [1, 2, 3, None]},
    "state": {"type": ["string", "null"], "enum": ["on", "off", "toggle", None]},
    "color": {"type": ["string", "null"], "enum": ["OFF", "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "MAGENTA", "WHITE", None]},
    "frequency_hz": {"type": ["integer", "null"], "minimum": 150, "maximum": 3000},
    "duration_ms": {"type": ["integer", "null"], "minimum": 30, "maximum": 1500},
    "strength": {"type": ["integer", "null"], "minimum": 30, "maximum": 180},
    "count": {"type": ["integer", "null"], "minimum": 1, "maximum": 6},
    "interval_ms": {"type": ["integer", "null"], "minimum": 50, "maximum": 500},
}
STEP_REQUIRED = list(STEP_PROPERTIES)
CUSTOM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "description": "Short lowercase command name using letters, digits, underscores."},
        "description": {"type": "string", "description": "One-sentence description, at most 120 characters."},
        "steps": {
            "type": "array", "minItems": 1, "maxItems": MAX_STEPS,
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": STEP_PROPERTIES,
                "required": STEP_REQUIRED,
            },
        },
    },
    "required": ["name", "description", "steps"],
}

SYSTEM_PROMPT = f"""You create custom commands for CLM-1, a Let's Start Coding Code Lab Mini controller.
Return only a JSON object matching the supplied schema. Never return source code, shell commands,
Python, C++, raw serial strings, file paths, or instructions to run commands on the Chromebook.
A command is a short sequence of safe, declarative device actions.

Allowed actions and fields:
- led: led=1 red, 2 green, 3 blue; state=on/off/toggle.
- color: color=OFF, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, WHITE.
- beep: frequency_hz 150..3000; duration_ms 30..1500.
- motor: strength 30..180; duration_ms 30..1500. Use sparingly.
- wait: duration_ms 30..1500.
- blink: led=1..3; count=1..6; interval_ms=50..500.

Every step object must include every schema field. Put null in every unused field.
Use 1..{MAX_STEPS} steps, and keep total elapsed time at or below {MAX_TOTAL_MS} milliseconds.
Keep effects family-friendly. Use a distinct name: lowercase letters, digits and underscores,
starting with a letter, 2..24 characters. Do not reuse built-in CLM command names.
Prefer interesting, varied but short sequences. No infinite loops, no network activity, no filesystem
operations, no keyboard injection, no high-power behavior, and no arbitrary pin access.
"""


def _secure_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    _secure_mkdir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            path.chmod(mode)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_settings() -> dict[str, Any]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    _atomic_write(SETTINGS_FILE, json.dumps(settings, indent=2) + "\n", 0o600)


def get_model() -> str:
    model = str(load_settings().get("model", DEFAULT_MODEL))
    return model if MODEL_RE.fullmatch(model) else DEFAULT_MODEL


def set_model(model: str) -> None:
    if not MODEL_RE.fullmatch(model):
        raise ValueError("Model name may contain letters, numbers, dots, underscores, colons and hyphens.")
    settings = load_settings()
    settings["model"] = model
    save_settings(settings)


def get_api_key() -> str | None:
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        value = KEY_FILE.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def key_source() -> str:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "OPENAI_API_KEY environment variable"
    if KEY_FILE.exists():
        return str(KEY_FILE)
    return "not configured"


def setup_key() -> bool:
    print("OpenAI API key setup")
    print("Your key is entered locally and hidden while typing. Keep it private; do not include it in source files or support requests.")
    try:
        key = getpass.getpass("API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return False
    if len(key) < 20 or any(ch.isspace() for ch in key):
        print("That doesn't look like a valid API key. Nothing was saved.")
        return False
    _atomic_write(KEY_FILE, key + "\n", 0o600)
    print(f"Saved locally with owner-only permissions: {KEY_FILE}")
    print("Next, run `ai test` to check the key, then `ai create ...` to make a command.")
    return True


def forget_key() -> None:
    try:
        KEY_FILE.unlink()
        print("Saved API key removed.")
    except FileNotFoundError:
        print("No saved API key was found.")
    if os.environ.get("OPENAI_API_KEY"):
        print("Note: OPENAI_API_KEY is still set in this terminal environment.")


def _http_json(url: str, api_key: str, payload: dict[str, Any] | None = None, timeout: int = 45) -> dict[str, Any]:
    headers = {"Authorization": "Bearer " + api_key, "Accept": "application/json"}
    data = None
    method = "GET"
    if payload is not None:
        method = "POST"
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000)
    except urllib.error.HTTPError as exc:
        # API error bodies are useful, but never include request headers or the key.
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
            details = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            details = f"HTTP {exc.code}"
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach the OpenAI API: {exc}") from None
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("The API returned a response that was not valid JSON.") from None
    if not isinstance(result, dict):
        raise RuntimeError("The API returned an unexpected response format.")
    return result


def test_api_key() -> None:
    key = get_api_key()
    if not key:
        raise RuntimeError("No API key is configured. Run `ai setup` first.")
    result = _http_json(MODELS_URL, key, timeout=25)
    if isinstance(result.get("data"), list):
        print(f"[ai] API key accepted. CLM is configured to use model {get_model()}.")
        print("[ai] Model access is checked when you create a command.")
    else:
        print("[ai] API key responded, but the model list format was unexpected.")


def _extract_output_text(response: dict[str, Any]) -> str:
    if response.get("status") == "incomplete":
        reason = response.get("incomplete_details") or {}
        raise RuntimeError(f"AI response was incomplete ({reason.get('reason', 'unknown reason')}). Try a shorter request.")
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise RuntimeError("The AI declined that command request. Try describing a harmless LED/sound/vibration sequence.")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    if not chunks:
        raise RuntimeError("The AI returned no command definition. Try rephrasing the request.")
    return "\n".join(chunks)


def validate_definition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"name", "description", "steps"}:
        raise ValueError("AI output must contain only name, description, and steps.")
    name = value["name"]
    description = value["description"]
    steps = value["steps"]
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError("AI chose an invalid command name. Names must be 2-24 lowercase letters/digits/underscores and start with a letter.")
    if not isinstance(description, str) or not description.strip() or len(description) > 120:
        raise ValueError("Command description must be 1-120 characters.")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"A command needs 1-{MAX_STEPS} steps.")

    clean_steps: list[dict[str, Any]] = []
    total_ms = 0
    keys = set(STEP_PROPERTIES)
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or set(step) != keys:
            raise ValueError(f"Step {idx} has missing or unexpected fields.")
        action = step.get("action")
        if action not in ("led", "color", "beep", "motor", "wait", "blink"):
            raise ValueError(f"Step {idx} uses an unsupported action.")
        s = dict(step)
        # Strict per-action validation; unused fields must be null.
        nullable_fields = {k: v for k, v in s.items() if k != "action"}
        required_nonnull: set[str]
        allowed_values: dict[str, tuple[Any, ...]] = {}
        duration = 0
        if action == "led":
            required_nonnull = {"led", "state"}
            allowed_values = {"state": ("on", "off", "toggle")}
            if type(s["led"]) is not int or s["led"] not in (1, 2, 3):
                raise ValueError(f"Step {idx}: LED must be 1, 2, or 3.")
            duration = 80
        elif action == "color":
            required_nonnull = {"color"}
            allowed_values = {"color": tuple(COLORS)}
            duration = 80
        elif action == "beep":
            required_nonnull = {"frequency_hz", "duration_ms"}
            if type(s["frequency_hz"]) is not int or not 150 <= s["frequency_hz"] <= 3000:
                raise ValueError(f"Step {idx}: frequency must be 150-3000 Hz.")
            if type(s["duration_ms"]) is not int or not 30 <= s["duration_ms"] <= 1500:
                raise ValueError(f"Step {idx}: beep duration must be 30-1500 ms.")
            duration = s["duration_ms"] + 40
        elif action == "motor":
            required_nonnull = {"strength", "duration_ms"}
            if type(s["strength"]) is not int or not 30 <= s["strength"] <= 180:
                raise ValueError(f"Step {idx}: motor strength must be 30-180.")
            if type(s["duration_ms"]) is not int or not 30 <= s["duration_ms"] <= 1500:
                raise ValueError(f"Step {idx}: motor duration must be 30-1500 ms.")
            duration = s["duration_ms"] + 40
        elif action == "wait":
            required_nonnull = {"duration_ms"}
            if type(s["duration_ms"]) is not int or not 30 <= s["duration_ms"] <= 1500:
                raise ValueError(f"Step {idx}: wait must be 30-1500 ms.")
            duration = s["duration_ms"]
        else:  # blink
            required_nonnull = {"led", "count", "interval_ms"}
            if type(s["led"]) is not int or s["led"] not in (1, 2, 3):
                raise ValueError(f"Step {idx}: blink LED must be 1, 2, or 3.")
            if type(s["count"]) is not int or not 1 <= s["count"] <= 6:
                raise ValueError(f"Step {idx}: blink count must be 1-6.")
            if type(s["interval_ms"]) is not int or not 50 <= s["interval_ms"] <= 500:
                raise ValueError(f"Step {idx}: blink interval must be 50-500 ms.")
            duration = s["count"] * 2 * s["interval_ms"] + 80

        for field in keys - {"action"}:
            if field in required_nonnull:
                if s[field] is None:
                    raise ValueError(f"Step {idx}: {field} is required for action {action}.")
            elif s[field] is not None:
                raise ValueError(f"Step {idx}: {field} is not used by action {action} and must be null.")
        for field, allowed in allowed_values.items():
            if s[field] not in allowed:
                raise ValueError(f"Step {idx}: invalid {field} value.")
        total_ms += duration
        if total_ms > MAX_TOTAL_MS:
            raise ValueError(f"Command is too long ({total_ms} ms). Maximum is {MAX_TOTAL_MS} ms.")
        clean_steps.append(s)

    return {"name": name, "description": description.strip(), "steps": clean_steps, "estimated_ms": total_ms}


def create_definition(description: str) -> dict[str, Any]:
    if not description.strip():
        raise ValueError("Describe the command after `ai create`.")
    if len(description) > 500:
        raise ValueError("Command idea is too long (maximum 500 characters).")
    key = get_api_key()
    if not key:
        raise RuntimeError("No API key is configured. Run `ai setup` first.")
    model = get_model()
    payload = {
        "model": model,
        "store": False,
        "max_output_tokens": 1800,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description.strip()},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "clm_custom_command",
                "strict": True,
                "schema": CUSTOM_SCHEMA,
            }
        },
    }
    response = _http_json(API_URL, key, payload, timeout=60)
    text = _extract_output_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI returned invalid JSON near character {exc.pos}.") from None
    result = validate_definition(data)
    result["model"] = model
    return result


def load_commands() -> dict[str, dict[str, Any]]:
    try:
        root = json.loads(COMMANDS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        print(f"[ai] Warning: couldn't read {COMMANDS_FILE}; custom commands are unavailable until repaired.")
        return {}
    commands = root.get("commands", {}) if isinstance(root, dict) else {}
    if not isinstance(commands, dict):
        return {}
    safe: dict[str, dict[str, Any]] = {}
    for name, definition in commands.items():
        try:
            clean = validate_definition(definition)
            if clean["name"] == name and name not in RESERVED_COMMANDS:
                safe[name] = clean
        except (ValueError, TypeError, KeyError):
            continue
    return safe


def save_commands(commands: dict[str, dict[str, Any]]) -> None:
    _secure_mkdir(APP_DIR)
    stored: dict[str, dict[str, Any]] = {}
    for name, definition in commands.items():
        raw = {key: definition[key] for key in ("name", "description", "steps") if key in definition}
        clean = validate_definition(raw)
        if name != clean["name"]:
            raise ValueError("Custom command key/name mismatch.")
        if name in RESERVED_COMMANDS:
            raise ValueError(f"`{name}` is reserved by CLM.")
        stored[name] = {"name": clean["name"], "description": clean["description"], "steps": clean["steps"]}
    payload = {"format_version": 1, "commands": stored}
    _atomic_write(COMMANDS_FILE, json.dumps(payload, indent=2) + "\n", 0o600)


def preview(definition: dict[str, Any]) -> None:
    print(f"\nAI command: {definition['name']}")
    print(definition["description"])
    print(f"Estimated run time: {definition.get('estimated_ms', 0) / 1000:.1f} seconds")
    print("Steps:")
    for index, step in enumerate(definition["steps"], start=1):
        action = step["action"]
        if action == "led":
            detail = f"LED {step['led']} → {step['state']}"
        elif action == "color":
            detail = f"Color → {step['color']}"
        elif action == "beep":
            detail = f"Beep {step['frequency_hz']} Hz for {step['duration_ms']} ms"
        elif action == "motor":
            detail = f"Vibrate strength {step['strength']} for {step['duration_ms']} ms"
        elif action == "wait":
            detail = f"Wait {step['duration_ms']} ms"
        else:
            detail = f"Blink LED {step['led']} {step['count']} times ({step['interval_ms']} ms)"
        print(f"  {index:02d}. {detail}")


def step_to_device_command(step: dict[str, Any]) -> tuple[str | None, float]:
    action = step["action"]
    if action == "led":
        return f"LED {step['led']} {step['state'].upper()}", 0.08
    if action == "color":
        return f"COLOR {step['color']}", 0.08
    if action == "beep":
        return f"BEEP {step['frequency_hz']} {step['duration_ms']}", step["duration_ms"] / 1000 + 0.06
    if action == "motor":
        return f"MOTOR {step['strength']} {step['duration_ms']}", step["duration_ms"] / 1000 + 0.06
    if action == "wait":
        return None, step["duration_ms"] / 1000
    if action == "blink":
        duration = step["count"] * 2 * step["interval_ms"] / 1000 + 0.12
        return f"BLINK {step['led']} {step['count']} {step['interval_ms']}", duration
    raise ValueError("Unsupported custom action")

RESERVED_COMMANDS = {
    "help", "?", "version", "device", "scan", "ports", "devices", "ping", "info",
    "status", "buttons", "stream", "reconnect", "echo", "led", "color", "colour",
    "rgb", "blink", "chase", "wave", "rainbow", "party", "siren", "alarm", "laser",
    "powerup", "explosion", "heartbeat", "countdown", "melody", "demo", "random",
    "dice", "coin", "ledtest", "glitch", "beacon", "portal", "fireworks", "hyperspace",
    "beep", "tone", "stop", "motor", "buzz", "pulse", "knob", "sos", "morse",
    "reset", "panic", "quit", "exit", "clear", "ascii", "joke", "fortune", "magic8",
    "time", "uptime", "whoami", "credits", "roll", "rps", "ai", "custom", "run",
    "clm_h@cker_init",
}


def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return False
    return answer in ("y", "yes")


def handle_ai_command(args: list[str]) -> bool:
    if not args or args[0].lower() in ("help", "?"):
        print("""AI COMMAND BUILDER
  ai setup                 Enter and securely save an OpenAI API key
  ai test                  Check whether the saved API key works
  ai status                Show AI configuration (never reveals the key)
  ai model [MODEL]         Show or change the model (default: gpt-6-luna)
  ai create DESCRIPTION    Ask AI to design a saved CLM hardware command
  ai forget                Remove the locally saved API key

CUSTOM COMMANDS
  custom list              List saved AI-made commands
  custom show NAME         Preview a saved command
  custom remove NAME       Delete a saved command
  custom run NAME          Run a saved command

Example:
  ai create make a blue comet: blink blue five times with a high beep
  blue_comet

Generated commands use a restricted action list. They cannot run shell,
Python, C++, arbitrary serial data, or access Chromebook files.""")
        return True

    sub = args[0].lower()
    if sub in ("setup", "key", "import"):
        setup_key()
        return True
    if sub == "test":
        try:
            test_api_key()
        except RuntimeError as exc:
            print(f"[ai] {exc}")
        return True
    if sub == "status":
        key_present = get_api_key() is not None
        print("AI integration: " + ("configured" if key_present else "not configured"))
        print("Key source: " + key_source())
        print("Model: " + get_model())
        print("Custom commands: " + str(len(load_commands())))
        return True
    if sub == "model":
        if len(args) == 1:
            print("Current model: " + get_model())
            return True
        if len(args) != 2:
            print("Usage: ai model [MODEL]")
            return True
        try:
            set_model(args[1])
            print("[ai] Model set to " + get_model())
        except ValueError as exc:
            print("[ai] " + str(exc))
        return True
    if sub == "forget":
        if _confirm("Remove the saved OpenAI API key? [y/N] "):
            forget_key()
        else:
            print("Key kept.")
        return True
    if sub == "create":
        description = " ".join(args[1:]).strip()
        if not description:
            print('Usage: ai create "describe the command you want"')
            return True
        print(f"[ai] Sending a command-generation request to {get_model()} (API usage may be billed)...")
        try:
            definition = create_definition(description)
            name = definition["name"]
            if name in RESERVED_COMMANDS:
                raise ValueError(f"AI chose `{name}`, which is reserved by CLM. Try a more specific description.")
            commands = load_commands()
            if name in commands and not _confirm(f"`{name}` already exists. Replace it? [y/N] "):
                print("Nothing changed.")
                return True
            preview(definition)
            if not _confirm("Save this command to CLM? [y/N] "):
                print("Not saved. Nothing was added to your command list.")
                return True
            commands[name] = definition
            save_commands(commands)
            print(f"[ai] Saved `{name}`. It is now a CLM command.")
            print(f"[ai] Run it by typing: {name}")
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"[ai] Could not create command: {exc}")
        return True

    print("Unknown AI command. Type `ai help`.")
    return True


def handle_custom_command(args: list[str], link: Any) -> bool:
    if not args or args[0].lower() in ("help", "list"):
        commands = load_commands()
        print("Saved CLM custom commands:")
        if not commands:
            print("  None yet. Try: ai create make a blue comet light effect")
        for name, definition in sorted(commands.items()):
            print(f"  {name:24} {definition['description']}")
        return True

    sub = args[0].lower()
    if sub in ("show", "remove", "delete", "run"):
        if len(args) != 2:
            print(f"Usage: custom {sub} NAME")
            return True
        name = args[1].lower()
        commands = load_commands()
        if name not in commands:
            print(f"No saved custom command named `{name}`.")
            return True
        definition = commands[name]
        if sub == "show":
            preview(definition)
            return True
        if sub in ("remove", "delete"):
            if _confirm(f"Delete custom command `{name}`? [y/N] "):
                del commands[name]
                save_commands(commands)
                print(f"[custom] Removed `{name}`.")
            else:
                print("Kept.")
            return True
        run_custom_command(definition, link)
        return True

    print("Usage: custom list | custom show NAME | custom run NAME | custom remove NAME")
    return True


def run_custom_command(definition: dict[str, Any], link: Any) -> None:
    if link is None or not getattr(getattr(link, "ser", None), "is_open", False):
        print("[custom] Connect the Code Lab Mini before running hardware commands.")
        return
    name = definition["name"]
    print(f"[custom] Running {name}: {definition['description']}")
    import time
    for index, step in enumerate(definition["steps"], start=1):
        try:
            device_command, delay_seconds = step_to_device_command(step)
        except (KeyError, ValueError) as exc:
            print(f"[custom] Invalid saved action at step {index}: {exc}")
            return
        if device_command and not link.send(device_command):
            print(f"[custom] Stopped at step {index}; device connection failed.")
            return
        if delay_seconds:
            time.sleep(delay_seconds)
    print(f"[custom] Finished {name}.")
