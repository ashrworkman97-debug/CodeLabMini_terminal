"""Offline tests for the CLM-1 setup diagnostics."""
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import clm_doctor


def fake_port(device="/dev/ttyUSB0", vid=0x0403, pid=0x6015):
    return SimpleNamespace(device=device, vid=vid, pid=pid)


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.serial = SimpleNamespace(__version__="3.5.0")

    def collect(self, ports=None, cli="/usr/bin/arduino-cli", firmware=True,
                python_version=(3, 12, 1)):
        list_ports = SimpleNamespace(comports=lambda: list(ports or []))
        firmware_path = Path("/tmp/clm_firmware.ino")
        with (
            patch.object(clm_doctor.sys, "version_info", python_version),
            patch.object(clm_doctor, "_load_serial", return_value=(self.serial, list_ports)),
            patch.object(clm_doctor.shutil, "which", return_value=cli),
            patch.object(
                clm_doctor, "_find_firmware",
                return_value=firmware_path if firmware else None,
                side_effect=None if firmware else FileNotFoundError("clm_firmware.ino not found"),
            ),
        ):
            return clm_doctor.collect_diagnostics()

    def test_reports_a_ready_device_and_firmware(self):
        checks = self.collect(ports=[fake_port()])
        statuses = {check.name: check.status for check in checks}
        self.assertEqual(statuses["Python"], "OK")
        self.assertEqual(statuses["pySerial"], "OK")
        self.assertEqual(statuses["Code Lab Mini"], "OK")
        self.assertEqual(statuses["Arduino CLI"], "OK")
        self.assertEqual(statuses["Firmware sketch"], "OK")

    def test_missing_device_is_a_warning_not_a_failure(self):
        checks = self.collect(ports=[], cli=None)
        statuses = {check.name: check.status for check in checks}
        self.assertEqual(statuses["Code Lab Mini"], "WARN")
        self.assertEqual(statuses["Arduino CLI"], "INFO")

    def test_other_serial_ports_are_reported(self):
        checks = self.collect(ports=[fake_port("/dev/ttyACM0", 0x2341, 0x0043)])
        device_check = next(check for check in checks if check.name == "Code Lab Mini")
        self.assertEqual(device_check.status, "WARN")
        self.assertIn("/dev/ttyACM0", device_check.detail)

    def test_missing_pyserial_is_a_required_failure(self):
        with patch.object(clm_doctor, "_load_serial", side_effect=ImportError("serial")):
            checks = clm_doctor.collect_diagnostics()
        serial_check = next(check for check in checks if check.name == "pySerial")
        self.assertEqual(serial_check.status, "FAIL")

    def test_old_python_is_a_required_failure(self):
        checks = self.collect(python_version=(3, 9, 9))
        python_check = next(check for check in checks if check.name == "Python")
        self.assertEqual(python_check.status, "FAIL")

    def test_doctor_prints_a_summary_and_returns_success_with_only_warnings(self):
        output = io.StringIO()
        with patch.object(
            clm_doctor, "collect_diagnostics",
            return_value=[clm_doctor.Diagnostic("WARN", "Code Lab Mini", "Not connected.")],
        ):
            result = clm_doctor.run_doctor(output)
        self.assertEqual(result, 0)
        self.assertIn("1 warning(s)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
