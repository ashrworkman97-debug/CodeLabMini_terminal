"""Offline regression tests for safe CLM-1 self-update archive validation."""
import builtins
import contextlib
import io
import runpy
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


    def test_transactional_replacement_updates_all_files(self):
        """Install every staged file when all replacements succeed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_a = root / "new-a"
            source_b = root / "new-b"
            target_a = root / "app" / "a"
            target_b = root / "app" / "b"
            target_a.parent.mkdir()
            source_a.write_text("new a", encoding="utf-8")
            source_b.write_text("new b", encoding="utf-8")
            target_a.write_text("old a", encoding="utf-8")
            target_b.write_text("old b", encoding="utf-8")

            clm_update._replace_files_transactionally([
                (source_a, target_a), (source_b, target_b),
            ])

            self.assertEqual(target_a.read_text(encoding="utf-8"), "new a")
            self.assertEqual(target_b.read_text(encoding="utf-8"), "new b")
            self.assertEqual({path.name for path in target_a.parent.iterdir()}, {"a", "b"})

    def test_staging_failure_leaves_existing_files_untouched(self):
        """Do not replace any destination until every source has been staged."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_a, source_b = root / "new-a", root / "new-b"
            target_a, target_b = root / "app" / "a", root / "app" / "b"
            target_a.parent.mkdir()
            source_a.write_text("new a", encoding="utf-8")
            source_b.write_text("new b", encoding="utf-8")
            target_a.write_text("old a", encoding="utf-8")
            target_b.write_text("old b", encoding="utf-8")
            real_copy = clm_update.shutil.copy2
            calls = 0

            def fail_second_copy(source, destination, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated staging failure")
                return real_copy(source, destination, *args, **kwargs)

            with patch("clm_update.shutil.copy2", side_effect=fail_second_copy):
                with self.assertRaisesRegex(OSError, "staging failure"):
                    clm_update._replace_files_transactionally([
                        (source_a, target_a), (source_b, target_b),
                    ])

            self.assertEqual(target_a.read_text(encoding="utf-8"), "old a")
            self.assertEqual(target_b.read_text(encoding="utf-8"), "old b")
            self.assertEqual({path.name for path in target_a.parent.iterdir()}, {"a", "b"})

    def test_replacement_failure_rolls_back_prior_files(self):
        """Restore old files if a later atomic replacement fails."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_a, source_b = root / "new-a", root / "new-b"
            target_a, target_b = root / "app" / "a", root / "app" / "b"
            target_a.parent.mkdir()
            source_a.write_text("new a", encoding="utf-8")
            source_b.write_text("new b", encoding="utf-8")
            target_a.write_text("old a", encoding="utf-8")
            target_b.write_text("old b", encoding="utf-8")
            real_replace = clm_update.os.replace
            calls = 0

            def fail_fourth_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("simulated replacement failure")
                return real_replace(source, destination)

            with patch("clm_update.os.replace", side_effect=fail_fourth_replace):
                with self.assertRaisesRegex(OSError, "replacement failure"):
                    clm_update._replace_files_transactionally([
                        (source_a, target_a), (source_b, target_b),
                    ])

            self.assertEqual(target_a.read_text(encoding="utf-8"), "old a")
            self.assertEqual(target_b.read_text(encoding="utf-8"), "old b")
            self.assertEqual({path.name for path in target_a.parent.iterdir()}, {"a", "b"})

    def test_legacy_update_missing_doctor_module_gets_recovery_guidance(self):
        """Keep the 1.6.0-to-1.7.0 first update usable before doctor is copied."""
        entrypoint = Path(__file__).resolve().parents[1] / "clm"
        namespace = runpy.run_path(str(entrypoint))
        run_doctor = namespace["run_doctor"]
        original_import = builtins.__import__

        def without_new_doctor(name, *args, **kwargs):
            if name == "clm_doctor":
                raise ModuleNotFoundError("No module named 'clm_doctor'", name="clm_doctor")
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch("builtins.__import__", side_effect=without_new_doctor):
            with contextlib.redirect_stdout(output):
                result = run_doctor()

        self.assertEqual(result, 1)
        self.assertIn("Run `clm update` once more", output.getvalue())

    def test_legacy_doctor_fallback_does_not_hide_other_import_errors(self):
        """Only a missing doctor module gets the legacy-update recovery message."""
        entrypoint = Path(__file__).resolve().parents[1] / "clm"
        namespace = runpy.run_path(str(entrypoint))
        run_doctor = namespace["run_doctor"]
        original_import = builtins.__import__

        def with_missing_dependency(name, *args, **kwargs):
            if name == "clm_doctor":
                raise ModuleNotFoundError("No module named 'serial'", name="serial")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=with_missing_dependency):
            with self.assertRaisesRegex(ModuleNotFoundError, "serial"):
                run_doctor()


if __name__ == "__main__":
    unittest.main()
