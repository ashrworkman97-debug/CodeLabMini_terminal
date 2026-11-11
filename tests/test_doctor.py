"""Offline tests for the CLM-1 setup diagnostics."""
import builtins
import contextlib
import runpy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import clm_doctor


def fake_port(device="/dev/ttyUSB0", vid=0x0403, pid=0x6015):
    """Build a lightweight fake serial-port record for diagnostic tests."""
    return SimpleNamespace(device=device, vid=vid, pid=pid)


class DoctorTests(unittest.TestCase):
    """Verify diagnostic output and legacy-upgrade behavior without hardware."""

    def test_cli_import_and_update_path_survive_missing_doctor_module(self):
        """Keep the command usable when a 1.6.0 updater has not copied clm_doctor.py."""
        cli_path = Path(__file__).resolve().parents[1] / "clm"
        real_import = builtins.__import__

        def import_without_doctor(name, *args, **kwargs):
            """Simulate an installation where the diagnostics module is absent."""
            if name == "clm_doctor":
                raise ModuleNotFoundError("missing during legacy upgrade", name="clm_doctor")
            return real_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch("builtins.__import__", side_effect=import_without_doctor):
            namespace = runpy.run_path(str(cli_path))
            with contextlib.redirect_stdout(output):
                self.assertEqual(namespace["run_doctor"](), 1)

        self.assertIn("Run `clm update` once more", output.getvalue())
        self.assertIn("finish the CLM-1 upgrade", output.getvalue())

    def test_cli_import_and_update_path_json_survive_missing_doctor_module(self):
        """Return a structured failure when a legacy upgrade lacks clm_doctor.py."""
        cli_path = Path(__file__).resolve().parents[1] / "clm"
        real_import = builtins.__import__

        def import_without_doctor(name, *args, **kwargs):
            """Simulate the first update pass before the new module is copied."""
            if name == "clm_doctor":
                raise ModuleNotFoundError("missing during legacy upgrade", name="clm_doctor")
            return real_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch("builtins.__import__", side_effect=import_without_doctor):
            namespace = runpy.run_path(str(cli_path))
            with contextlib.redirect_stdout(output):
                result = namespace["run_doctor"](json_output=True)

        report = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["summary"]["fail"], 1)
        self.assertEqual(report["exit_code"], 1)
        self.assertIn("finish the CLM-1 upgrade", report["checks"][0]["detail"])

    def setUp(self):
        """Prepare a fake pySerial package for each test."""
        self.serial = SimpleNamespace(__version__="3.5.0")

    def collect(self, ports=None, cli="/usr/bin/arduino-cli", firmware=True,
                python_version=(3, 12, 1), port_access=True):
        """Collect checks with controlled Python, USB, Arduino CLI, and firmware state."""
        list_ports = SimpleNamespace(comports=lambda: list(ports or []))
        firmware_path = Path("/tmp/clm_firmware.ino")
        with (
            patch.object(clm_doctor.sys, "version_info", python_version),
            patch.object(clm_doctor, "_load_serial", return_value=(self.serial, list_ports)),
            patch.object(clm_doctor.shutil, "which", return_value=cli),
            patch.object(clm_doctor.os, "access", return_value=port_access),
            patch.object(
                clm_doctor, "_find_firmware",
                return_value=firmware_path if firmware else None,
                side_effect=None if firmware else FileNotFoundError("clm_firmware.ino not found"),
            ),
        ):
            return clm_doctor.collect_diagnostics()

    def test_reports_a_ready_device_and_firmware(self):
        """Report all required checks as healthy when the Mini is available."""
        checks = self.collect(ports=[fake_port()])
        statuses = {check.name: check.status for check in checks}
        self.assertEqual(statuses["Python"], "OK")
        self.assertEqual(statuses["pySerial"], "OK")
        self.assertEqual(statuses["Code Lab Mini"], "OK")
        self.assertEqual(statuses["Arduino CLI"], "OK")
        self.assertEqual(statuses["Firmware sketch"], "OK")

    def test_missing_device_is_a_warning_not_a_failure(self):
        """Treat an unplugged Mini and optional Arduino CLI as non-fatal."""
        checks = self.collect(ports=[], cli=None)
        statuses = {check.name: check.status for check in checks}
        self.assertEqual(statuses["Code Lab Mini"], "WARN")
        self.assertEqual(statuses["Arduino CLI"], "INFO")

    def test_other_serial_ports_are_reported(self):
        """Show visible serial ports that do not match the Mini's USB ID."""
        checks = self.collect(ports=[fake_port("/dev/ttyACM0", 0x2341, 0x0043)])
        device_check = next(check for check in checks if check.name == "Code Lab Mini")
        self.assertEqual(device_check.status, "WARN")
        self.assertIn("/dev/ttyACM0", device_check.detail)

    def test_usb_permissions_are_reported_when_accessible(self):
        """Report successful read/write access without opening the serial port."""
        with patch.object(clm_doctor.sys, "platform", "linux"):
            checks = self.collect(ports=[fake_port()], port_access=True)
        permission_check = next(check for check in checks if check.name == "USB permissions")
        self.assertEqual(permission_check.status, "OK")
        self.assertIn("Read/write access", permission_check.detail)

    def test_usb_permission_warning_includes_linux_group_guidance(self):
        """Explain a common Linux serial-device permission fix."""
        with patch.object(clm_doctor.sys, "platform", "linux"):
            checks = self.collect(ports=[fake_port()], port_access=False)
        permission_check = next(check for check in checks if check.name == "USB permissions")
        self.assertEqual(permission_check.status, "WARN")
        self.assertIn("dialout", permission_check.detail)
        self.assertIn("usermod -aG", permission_check.detail)

    def test_windows_skips_unix_device_node_permission_check(self):
        """Avoid treating Windows COM ports as Unix filesystem paths."""
        with patch.object(clm_doctor.sys, "platform", "win32"):
            with patch.object(clm_doctor.os, "access") as access:
                check = clm_doctor._check_usb_permissions([fake_port("COM3")])
        access.assert_not_called()
        self.assertEqual(check.status, "INFO")

    def test_missing_pyserial_is_a_required_failure(self):
        """Mark the missing required pySerial dependency as a failure."""
        with patch.object(clm_doctor, "_load_serial", side_effect=ImportError("serial")):
            checks = clm_doctor.collect_diagnostics()
        serial_check = next(check for check in checks if check.name == "pySerial")
        self.assertEqual(serial_check.status, "FAIL")

    def test_old_python_is_a_required_failure(self):
        """Reject Python versions below the supported minimum."""
        checks = self.collect(python_version=(3, 9, 9))
        python_check = next(check for check in checks if check.name == "Python")
        self.assertEqual(python_check.status, "FAIL")

    def test_json_report_is_machine_readable_and_has_a_stable_summary(self):
        """Keep JSON fields and summary counts predictable for scripts."""
        checks = [
            clm_doctor.Diagnostic("OK", "Python", "3.13.0"),
            clm_doctor.Diagnostic("WARN", "Code Lab Mini", "Not connected."),
            clm_doctor.Diagnostic("INFO", "Arduino CLI", "Optional."),
        ]
        output = io.StringIO()
        with patch.object(clm_doctor, "collect_diagnostics", return_value=checks):
            result = clm_doctor.run_doctor(output, json_output=True)

        report = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["summary"], {"ok": 1, "warn": 1, "info": 1, "fail": 0})
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["checks"][0], {
            "status": "OK", "name": "Python", "detail": "3.13.0",
        })

    def test_json_report_returns_nonzero_for_required_failures(self):
        """Include required failures in the JSON report and process status."""
        checks = [clm_doctor.Diagnostic("FAIL", "pySerial", "Not installed.")]
        output = io.StringIO()
        with patch.object(clm_doctor, "collect_diagnostics", return_value=checks):
            result = clm_doctor.run_doctor(output, json_output=True)

        report = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(report["summary"]["fail"], 1)
        self.assertEqual(report["exit_code"], 1)

    def test_cli_accepts_doctor_json_option(self):
        """Route the top-level --json option to the diagnostic formatter."""
        cli_path = Path(__file__).resolve().parents[1] / "clm"
        namespace = runpy.run_path(str(cli_path))
        with patch.object(clm_doctor, "run_doctor", return_value=0) as doctor:
            self.assertEqual(namespace["main"](["doctor", "--json"]), 0)
        doctor.assert_called_once_with(json_output=True, strict=False)

    def test_doctor_prints_a_summary_and_returns_success_with_only_warnings(self):
        """Return success when diagnostics contain warnings but no failures."""
        output = io.StringIO()
        with patch.object(
            clm_doctor, "collect_diagnostics",
            return_value=[clm_doctor.Diagnostic("WARN", "Code Lab Mini", "Not connected.")],
        ):
            result = clm_doctor.run_doctor(output)
        self.assertEqual(result, 0)
        self.assertIn("1 warning(s)", output.getvalue())

    def test_strict_mode_treats_warnings_as_nonzero(self):
        """Make warnings fail strict checks without changing their diagnostic severity."""
        output = io.StringIO()
        checks = [
            clm_doctor.Diagnostic("WARN", "Code Lab Mini", "Not connected."),
            clm_doctor.Diagnostic("INFO", "Arduino CLI", "Optional."),
        ]
        with patch.object(clm_doctor, "collect_diagnostics", return_value=checks):
            result = clm_doctor.run_doctor(output, strict=True)
        self.assertEqual(result, 1)
        self.assertIn("[WARN] Code Lab Mini", output.getvalue())
        self.assertIn("Strict mode: warnings cause a non-zero exit code.", output.getvalue())

    def test_strict_json_report_marks_mode_and_fails_on_warnings(self):
        """Expose strict mode and its warning-sensitive exit code to scripts."""
        output = io.StringIO()
        checks = [clm_doctor.Diagnostic("WARN", "Code Lab Mini", "Not connected.")]
        with patch.object(clm_doctor, "collect_diagnostics", return_value=checks):
            result = clm_doctor.run_doctor(output, json_output=True, strict=True)
        report = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertTrue(report["strict"])
        self.assertEqual(report["summary"]["warn"], 1)
        self.assertEqual(report["exit_code"], 1)

    def test_cli_accepts_doctor_options_in_any_order(self):
        """Allow --json and --strict together in either order."""
        cli_path = Path(__file__).resolve().parents[1] / "clm"
        namespace = runpy.run_path(str(cli_path))
        for options in (["--json", "--strict"], ["--strict", "--json"]):
            with patch.object(clm_doctor, "run_doctor", return_value=0) as doctor:
                self.assertEqual(namespace["main"](["doctor", *options]), 0)
            doctor.assert_called_once_with(json_output=True, strict=True)


if __name__ == "__main__":
    unittest.main()
