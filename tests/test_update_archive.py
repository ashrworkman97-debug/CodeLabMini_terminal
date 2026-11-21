"""Offline regression tests for safe CLM-1 self-update archive validation."""
import contextlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import clm_update


class UpdateArchiveTests(unittest.TestCase):
    """Ensure incomplete downloads cannot partially replace a working install."""

    @staticmethod
    def make_archive(files):
        """Build a small codeload-style archive in memory."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, value in files.items():
                archive.writestr(f"CodeLabMini_terminal-main/{name}", value)
        return buffer.getvalue()

    def test_accepts_archive_with_every_required_core_file(self):
        """Accept a source tree containing all modules needed by the CLI."""
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            for name in clm_update.CORE_FILES:
                (source_root / name).write_text("# test file\n", encoding="utf-8")

            clm_update._validate_source_tree(source_root)

    def test_rejects_archive_missing_a_required_core_module(self):
        """Name missing core files before any installation work can begin."""
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            for name in clm_update.CORE_FILES:
                if name == "clm_update.py":
                    continue
                (source_root / name).write_text("# test file\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "clm_update.py"):
                clm_update._validate_source_tree(source_root)

    def test_incomplete_download_is_rejected_before_copying_files(self):
        """Leave the existing app directory untouched when a module is absent."""
        archive_data = self.make_archive({"clm": "# incomplete archive\n"})
        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory) / "app"
            config_dir = Path(directory) / "config"
            output = io.StringIO()

            with (
                patch(
                    "clm_update.urllib.request.urlopen",
                    return_value=io.BytesIO(archive_data),
                ),
                patch("clm_update.APP_DIR", app_dir),
                patch("clm_update.CONFIG_DIR", config_dir),
                patch("clm_update.shutil.copy2") as copy_file,
                contextlib.redirect_stdout(output),
            ):
                result = clm_update.install_update()

            self.assertEqual(result, 1)
            copy_file.assert_not_called()
            self.assertFalse(app_dir.exists())
            self.assertIn("No installed files were changed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
