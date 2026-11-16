"""Offline tests for cross-platform CLM-1 host identification."""
import contextlib
import io
import runpy
from pathlib import Path
import unittest
from unittest.mock import patch


CLI_PATH = Path(__file__).resolve().parents[1] / "clm"


class WhoAmITests(unittest.TestCase):
    """Verify whoami reports the actual host rather than assuming Linux."""

    def setUp(self):
        """Load the CLI entry point without starting the interactive console."""
        self.cli = runpy.run_path(str(CLI_PATH))

    def test_reports_host_and_python_details_on_supported_platforms(self):
        """Format host names consistently on Linux, macOS, and Windows."""
        cases = (
            ("Linux", "6.12", "3.13.1", "Linux 6.12"),
            ("Darwin", "15.1", "3.12.8", "macOS 15.1"),
            ("Windows", "11", "3.10.16", "Windows 11"),
        )
        for system, release, python_version, expected_host in cases:
            with self.subTest(system=system):
                output = io.StringIO()
                with (
                    patch("platform.system", return_value=system),
                    patch("platform.release", return_value=release),
                    patch("platform.python_version", return_value=python_version),
                    contextlib.redirect_stdout(output),
                ):
                    handled = self.cli["local_command"]("whoami", [], 0.0)

                self.assertTrue(handled)
                self.assertIn(f"Host: {expected_host}", output.getvalue())
                self.assertIn(f"Python: {python_version}", output.getvalue())
                self.assertIn("Device: Let's Start Coding Code Lab Mini", output.getvalue())


if __name__ == "__main__":
    unittest.main()
