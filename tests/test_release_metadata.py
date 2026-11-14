"""Regression tests for CLM-1 release metadata consistency."""
import re
import unittest
from pathlib import Path

from clm_update import CORE_FILES


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(name: str) -> str:
    """Read a UTF-8 project file relative to the repository root."""
    return (ROOT / name).read_text(encoding="utf-8")


def current_version() -> str:
    """Extract the CLI's authoritative application version."""
    source = read_project_file("clm")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', source, re.M)
    if not match:
        raise AssertionError("APP_VERSION was not found in the clm entry point")
    return match.group(1)


class ReleaseMetadataTests(unittest.TestCase):
    """Keep user-facing version declarations synchronized across releases."""

    def test_changelog_documents_current_cli_version(self):
        """Require a changelog heading for the version shipped by the CLI."""
        version = current_version()
        changelog = read_project_file("CHANGELOG.md")
        self.assertRegex(changelog, rf"(?m)^## {re.escape(version)} — .+$")

    def test_all_installers_match_current_cli_version(self):
        """Keep Linux, macOS, and Windows installer labels aligned with the CLI."""
        version = current_version()
        patterns = {
            "install.sh": r'^VERSION\s*=\s*"([^"]+)"$',
            "install_macos.sh": r'^VERSION\s*=\s*"([^"]+)"$',
            "install_windows.ps1": r'^\$Version\s*=\s*"([^"]+)"$',
        }
        for filename, pattern in patterns.items():
            with self.subTest(installer=filename):
                match = re.search(pattern, read_project_file(filename), re.M)
                self.assertIsNotNone(match, f"Version declaration missing in {filename}")
                self.assertEqual(match.group(1), version)

    def test_command_reference_matches_current_cli_version(self):
        """Keep the command-reference banner synchronized with the CLI."""
        version = current_version()
        first_line = read_project_file("COMMANDS.txt").splitlines()[0]
        self.assertEqual(first_line, f"CLM-1 v{version} — COMMAND REFERENCE")

    def test_new_updater_copies_the_diagnostic_module(self):
        """Ensure future self-updates install the lazily imported doctor module."""
        self.assertIn("clm_doctor.py", CORE_FILES)
        self.assertIn("clm_update.py", CORE_FILES)


if __name__ == "__main__":
    unittest.main()
