import unittest
from pathlib import Path
from clm_paths import get_app_dir, get_config_dir

class PlatformPathTests(unittest.TestCase):
    def setUp(self):
        self.home = Path("/home/tester")
    def test_linux_paths_preserve_existing_layout(self):
        self.assertEqual(get_app_dir(self.home, "linux"), self.home / ".local/share/clm-1")
        self.assertEqual(get_config_dir(self.home, "linux"), self.home / ".config/clm-1")
    def test_macos_uses_application_support(self):
        self.assertEqual(get_app_dir(self.home, "darwin"), self.home / "Library/Application Support/CLM-1")
        self.assertEqual(get_config_dir(self.home, "darwin"), self.home / "Library/Application Support/CLM-1/Config")
    def test_windows_uses_roaming_and_local_appdata(self):
        env = {"LOCALAPPDATA": r"C:\Users\tester\AppData\Local", "APPDATA": r"C:\Users\tester\AppData\Roaming"}
        self.assertEqual(get_app_dir(self.home, "win32", env), Path(env["LOCALAPPDATA"]) / "CLM-1")
        self.assertEqual(get_config_dir(self.home, "win32", env), Path(env["APPDATA"]) / "CLM-1")
    def test_windows_fallbacks(self):
        self.assertEqual(get_app_dir(self.home, "win32", {}), self.home / "AppData/Local/CLM-1")
        self.assertEqual(get_config_dir(self.home, "win32", {}), self.home / "AppData/Roaming/CLM-1")

if __name__ == "__main__":
    unittest.main()
