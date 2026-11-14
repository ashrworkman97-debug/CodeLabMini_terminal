"""Regression tests for diagnostics with multiple matching Code Lab Mini devices."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import clm_doctor


class MultipleDeviceDiagnosticsTests(unittest.TestCase):
    """Verify that ambiguous firmware targets are surfaced to the user."""

    def test_multiple_minis_warn_and_show_explicit_flasher_port(self):
        """Warn when the flasher cannot choose among multiple Mini devices."""
        ports = [
            SimpleNamespace(device="/dev/ttyUSB0", vid=0x0403, pid=0x6015),
            SimpleNamespace(device="/dev/ttyUSB1", vid=0x0403, pid=0x6015),
        ]
        serial = SimpleNamespace(__version__="3.5.0")
        list_ports = SimpleNamespace(comports=lambda: ports)

        with (
            patch.object(clm_doctor.sys, "version_info", (3, 12, 1)),
            patch.object(clm_doctor, "_load_serial", return_value=(serial, list_ports)),
            patch.object(clm_doctor.shutil, "which", return_value="/usr/bin/arduino-cli"),
            patch.object(clm_doctor, "_find_firmware", return_value=Path("/tmp/clm_firmware.ino")),
        ):
            checks = clm_doctor.collect_diagnostics()

        device_check = next(check for check in checks if check.name == "Code Lab Mini")
        self.assertEqual(device_check.status, "WARN")
        self.assertIn("/dev/ttyUSB0", device_check.detail)
        self.assertIn("/dev/ttyUSB1", device_check.detail)
        self.assertIn("clm_h@cker_init --port PORT", device_check.detail)


if __name__ == "__main__":
    unittest.main()
