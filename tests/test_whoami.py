"""Offline tests for cross-platform CLM-1 host identification."""
import contextlib
import io
import runpy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


CLI_PATH = Path(__file__).resolve().parents[1] / "clm"


class WhoAmITests(unittest.TestCase):
    """Verify whoami reports the actual host rather than kernel aliases."""

    def setUp(self):
        """Load the CLI entry point without starting the interactive console."""
        self.cli = runpy.run_path(str(CLI_PATH))

    def test_identifies_chromeos_crostini_from_milestone_marker(self):
        """Name the ChromeOS host when Crostini exposes its milestone marker."""
        output = io.StringIO()
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.release", return_value="6.6.44"),
            patch("platform.python_version", return_value="3.13.1"),
            patch("pathlib.Path.read_text", return_value="161"),
            contextlib.redirect_stdout(output),
        ):
            handled = self.cli["local_command"]("whoami", [], 0.0)

        self.assertTrue(handled)
        self.assertIn(
            "Host: ChromeOS M161 (Crostini Linux; kernel 6.6.44)",
            output.getvalue(),
        )

    def test_ignores_invalid_chromeos_milestone_marker(self):
        """Avoid labeling ordinary Linux as ChromeOS when the marker is malformed."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.release", return_value="6.12"),
            patch("pathlib.Path.read_text", return_value="not-a-milestone"),
        ):
            label = self.cli["host_os_label"]()

        self.assertEqual(label, "Linux 6.12")

    def test_reports_host_and_python_details_on_supported_platforms(self):
        """Use product versions for macOS and distinguish Windows 10/11."""
        cases = (
            ("Linux", "6.12", "3.13.1", "Linux 6.12", None, None),
            ("Darwin", "24.1.0", "3.12.8", "macOS 15.1", "15.1", None),
            ("Darwin", "24.1.0", "3.12.8", "macOS", "", None),
            ("Windows", "10", "3.10.16", "Windows 11", None, 22631),
            ("Windows", "10", "3.10.16", "Windows 10", None, 19045),
        )
        for system, release, python_version, expected_host, mac_version, windows_build in cases:
            with self.subTest(system=system, expected_host=expected_host):
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch("platform.system", return_value=system))
                    stack.enter_context(patch("platform.release", return_value=release))
                    stack.enter_context(
                        patch("platform.python_version", return_value=python_version)
                    )
                    if system == "Linux":
                        stack.enter_context(
                            patch("pathlib.Path.read_text", side_effect=FileNotFoundError)
                        )
                    if system == "Darwin":
                        stack.enter_context(
                            patch(
                                "platform.mac_ver",
                                return_value=(mac_version, ("", "", ""), "arm64"),
                            )
                        )
                    if system == "Windows":
                        stack.enter_context(
                            patch(
                                "sys.getwindowsversion",
                                return_value=SimpleNamespace(
                                    major=10, build=windows_build
                                ),
                                create=True,
                            )
                        )
                    stack.enter_context(contextlib.redirect_stdout(output))
                    handled = self.cli["local_command"]("whoami", [], 0.0)

                self.assertTrue(handled)
                self.assertIn(f"Host: {expected_host}", output.getvalue())
                self.assertIn(f"Python: {python_version}", output.getvalue())
                self.assertIn(
                    "Device: Let's Start Coding Code Lab Mini", output.getvalue()
                )


if __name__ == "__main__":
    unittest.main()
