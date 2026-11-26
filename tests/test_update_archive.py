"""Offline regression tests for safe CLM-1 self-update archive validation."""
import contextlib
import io
import tempfile
import unittest
import zipfile
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    @staticmethod
    def fake_member(filename, file_size=0, mode=0):
        """Create ZIP metadata without allocating a large archive payload."""
        return SimpleNamespace(
            filename=filename,
            file_size=file_size,
            external_attr=mode << 16,
            is_dir=lambda: filename.endswith("/"),
        )

    def test_extracts_a_normal_codeload_archive(self):
        """Extract ordinary files under the archive's single top-level directory."""
        archive_data = self.make_archive({"clm": "print('ok')", "clm_paths.py": "# paths"})
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
                clm_update._extract_archive_safely(archive, destination)

            source_root = destination / "CodeLabMini_terminal-main"
            self.assertEqual((source_root / "clm").read_text(encoding="utf-8"), "print('ok')")
            self.assertEqual((source_root / "clm_paths.py").read_text(encoding="utf-8"), "# paths")

    def test_rejects_unsafe_posix_and_windows_paths(self):
        """Reject traversal and drive-qualified names before opening archive members."""
        for filename in ("../outside", "source/../outside", "C:/outside", "source\\\\..\\\\outside"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                archive = Mock()
                archive.infolist.return_value = [self.fake_member(filename)]
                with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
                    clm_update._extract_archive_safely(archive, Path(directory) / "source")
                archive.open.assert_not_called()

    def test_rejects_symbolic_link_entries(self):
        """Never materialize archive symlinks in the temporary source tree."""
        archive = Mock()
        archive.infolist.return_value = [
            self.fake_member("source/link", mode=stat.S_IFLNK | 0o777)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Unsupported special file"):
                clm_update._extract_archive_safely(archive, Path(directory) / "source")
        archive.open.assert_not_called()

    def test_rejects_declared_oversized_archives_before_extraction(self):
        """Use ZIP metadata to reject oversized archives before writing any entry."""
        archive = Mock()
        archive.infolist.return_value = [
            self.fake_member("source/large.bin", file_size=9)
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(clm_update, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 8):
                with self.assertRaisesRegex(RuntimeError, "64 MiB safety limit"):
                    clm_update._extract_archive_safely(archive, Path(directory) / "source")
        archive.open.assert_not_called()

    def test_enforces_actual_expanded_size_when_zip_metadata_underreports(self):
        """Count streamed bytes instead of trusting the ZIP's declared file size."""
        class OversizedStream:
            def __init__(self):
                self.remaining = 9

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                count = min(4, self.remaining)
                self.remaining -= count
                return b"x" * count

        archive = Mock()
        archive.infolist.return_value = [
            self.fake_member("source/large.bin", file_size=0)
        ]
        archive.open.return_value = OversizedStream()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(clm_update, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 8):
                with self.assertRaisesRegex(RuntimeError, "64 MiB safety limit"):
                    clm_update._extract_archive_safely(archive, Path(directory) / "source")

    def test_rejects_archives_with_too_many_entries(self):
        """Bound ZIP metadata processing before creating extracted files."""
        archive = Mock()
        archive.infolist.return_value = [
            self.fake_member("source/one"), self.fake_member("source/two")
        ]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(clm_update, "MAX_ARCHIVE_MEMBERS", 1):
                with self.assertRaisesRegex(RuntimeError, "too many entries"):
                    clm_update._extract_archive_safely(archive, Path(directory) / "source")
        archive.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
