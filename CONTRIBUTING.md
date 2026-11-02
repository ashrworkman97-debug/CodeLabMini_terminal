# Contributing

Thanks for your interest in CLM-1.

## Before submitting changes

- Keep host commands and device firmware protocol changes in sync.
- Do not add API keys, local settings, personal custom-command libraries, or device-specific private data.
- Keep AI-generated macros declarative and validated. Do not add execution of arbitrary generated shell, Python, or C++ code.
- Document new commands in both `COMMANDS.txt` and `README.md`.
- Update `CHANGELOG.md` for user-visible changes.

## Run checks

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile clm clm_ai.py
bash -n install.sh
```

For firmware changes, also compile the sketch with a compatible AVR toolchain and test it on a Code Lab Mini when hardware is available. Clearly distinguish automated checks from physical-device tests in pull requests.

## Pull requests

Include a short summary, the reason for the change, test results, and any protocol or pin-mapping changes. Do not include API keys or private device logs.
