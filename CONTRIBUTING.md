# Contributing to CLM-1

Thanks for helping improve CLM-1! Bug reports, tested command ideas, hardware compatibility notes, and documentation fixes are welcome.

## Before submitting a change

- Keep host commands and the device firmware protocol in sync.
- Do not add API keys, local settings, personal custom-command libraries, or private device data.
- Keep AI-generated macros declarative and validated. Do not execute generated Python, shell, C++, or arbitrary serial commands.
- Document new or changed commands in both `COMMANDS.txt` and `README.md`.
- Add or update offline tests for host-side logic where practical.
- Update `CHANGELOG.md` for user-visible changes.

## Run checks locally

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile clm clm_ai.py clm_flash.py
bash -n install.sh
python3 clm --version
python3 clm --help
```

These checks do not require a connected Code Lab Mini or an OpenAI API key. The GitHub Actions workflow runs the same checks across supported Python versions.

For firmware changes, compile the sketch with a compatible AVR toolchain and test it on a Code Lab Mini when hardware is available. Clearly distinguish automated checks from physical-device tests in pull requests.

## Pull requests

Include a short summary, the reason for the change, test results, and any protocol or pin-mapping changes. Do not include API keys, private macros, or credentials in source files, commits, screenshots, or logs.

Use the pull request template to record the checks you ran and whether hardware testing was performed.
