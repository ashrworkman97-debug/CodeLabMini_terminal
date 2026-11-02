"""Offline tests for the direct firmware uploader."""
import unittest
from types import SimpleNamespace
from clm_flash import DEFAULT_FQBN, build_parser, select_port


def port(device, vid=None, pid=None):
    return SimpleNamespace(device=device, vid=vid, pid=pid)


class PortSelectionTests(unittest.TestCase):
    def test_auto_selects_ftdi_mini(self):
        selected, identified = select_port([
            port("/dev/ttyUSB0", 0x0403, 0x6015),
            port("/dev/ttyACM0", 0x2341, 0x0043),
        ])
        self.assertEqual(selected.device, "/dev/ttyUSB0")
        self.assertTrue(identified)

    def test_multiple_minis_require_explicit_port(self):
        with self.assertRaisesRegex(RuntimeError, "Multiple Code Lab Mini"):
            select_port([
                port("/dev/ttyUSB0", 0x0403, 0x6015),
                port("/dev/ttyUSB1", 0x0403, 0x6015),
            ])

    def test_unknown_port_is_not_auto_selected(self):
        with self.assertRaisesRegex(RuntimeError, "No Code Lab Mini"):
            select_port([port("/dev/ttyACM0", 0x2341, 0x0043)])

    def test_explicit_port_is_allowed_but_not_misidentified(self):
        selected, identified = select_port(
            [port("/dev/ttyACM0", 0x2341, 0x0043)], "/dev/ttyACM0"
        )
        self.assertEqual(selected.device, "/dev/ttyACM0")
        self.assertFalse(identified)

    def test_invisible_explicit_port_fails(self):
        with self.assertRaisesRegex(RuntimeError, "not visible"):
            select_port([port("/dev/ttyUSB0", 0x0403, 0x6015)], "/dev/ttyUSB9")


class ArgumentTests(unittest.TestCase):
    def test_defaults(self):
        options = build_parser().parse_args([])
        self.assertEqual(options.fqbn, DEFAULT_FQBN)
        self.assertIsNone(options.port)
        self.assertFalse(options.compile_only)

    def test_options(self):
        options = build_parser().parse_args([
            "--port", "/dev/ttyUSB0", "--fqbn", "arduino:avr:nano", "--compile-only"
        ])
        self.assertEqual(options.port, "/dev/ttyUSB0")
        self.assertEqual(options.fqbn, "arduino:avr:nano")
        self.assertTrue(options.compile_only)


if __name__ == "__main__":
    unittest.main()
