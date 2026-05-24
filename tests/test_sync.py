"""Tests unitaires du module :mod:`android_save.sync`."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from android_save.adb import RemoteFile
from android_save.sync import (
    FileStatus,
    LocalInventory,
    SyncEngine,
    SyncEntry,
    SyncPlan,
    format_size,
)


def make_remote(path: str, size: int = 100, mtime: float = 1_700_000_000.0) -> RemoteFile:
    return RemoteFile(path=path, size=size, mtime=mtime)


class TestLocalInventory:
    def test_scans_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("world")

        inv = LocalInventory(str(tmp_path)).scan()
        assert "a.txt" in inv
        assert "sub/b.txt" in inv or str(Path("sub") / "b.txt") in inv

    def test_empty_directory(self, tmp_path):
        inv = LocalInventory(str(tmp_path)).scan()
        assert inv == {}

    def test_nonexistent_directory(self):
        inv = LocalInventory("/does/not/exist").scan()
        assert inv == {}

    def test_returns_size_and_mtime(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"0" * 42)
        inv = LocalInventory(str(tmp_path)).scan()
        size, mtime = inv["file.txt"]
        assert size == 42
        assert mtime > 0


class TestSyncEngine:
    def setup_method(self):
        self.engine = SyncEngine(
            remote_root="/sdcard",
            local_root="/backup",
            mtime_tolerance=2.0,
        )

    def test_new_file_is_to_copy(self):
        remote = [make_remote("/sdcard/photo.jpg", size=500)]
        with patch.object(LocalInventory, "scan", return_value={}):
            plan = self.engine.compute(remote)
        assert plan.entries["photo.jpg"].status == FileStatus.TO_COPY

    def test_identical_file_skipped(self):
        remote = [make_remote("/sdcard/photo.jpg", size=500, mtime=1_700_000_000.0)]
        local = {"photo.jpg": (500, 1_700_000_000.0)}
        with patch.object(LocalInventory, "scan", return_value=local):
            plan = self.engine.compute(remote)
        assert plan.entries["photo.jpg"].status == FileStatus.IDENTICAL

    def test_size_mismatch_is_update(self):
        remote = [make_remote("/sdcard/photo.jpg", size=999, mtime=1_700_000_000.0)]
        local = {"photo.jpg": (500, 1_700_000_000.0)}
        with patch.object(LocalInventory, "scan", return_value=local):
            plan = self.engine.compute(remote)
        assert plan.entries["photo.jpg"].status == FileStatus.TO_UPDATE

    def test_mtime_within_tolerance_is_identical(self):
        remote = [make_remote("/sdcard/photo.jpg", size=500, mtime=1_700_000_001.0)]
        local = {"photo.jpg": (500, 1_700_000_000.0)}
        with patch.object(LocalInventory, "scan", return_value=local):
            plan = self.engine.compute(remote)
        assert plan.entries["photo.jpg"].status == FileStatus.IDENTICAL

    def test_mtime_beyond_tolerance_is_update(self):
        remote = [make_remote("/sdcard/photo.jpg", size=500, mtime=1_700_000_010.0)]
        local = {"photo.jpg": (500, 1_700_000_000.0)}
        with patch.object(LocalInventory, "scan", return_value=local):
            plan = self.engine.compute(remote)
        assert plan.entries["photo.jpg"].status == FileStatus.TO_UPDATE

    def test_local_only_file_is_orphan(self):
        local = {"orphan.txt": (100, 1_700_000_000.0)}
        with patch.object(LocalInventory, "scan", return_value=local):
            plan = self.engine.compute([])
        assert plan.entries["orphan.txt"].status == FileStatus.ORPHAN

    def test_path_traversal_ignored(self):
        remote = [make_remote("/sdcard/../etc/passwd", size=100)]
        with patch.object(LocalInventory, "scan", return_value={}):
            plan = self.engine.compute(remote)
        assert not any(".." in k for k in plan.entries)

    def test_nested_paths_handled(self):
        remote = [make_remote("/sdcard/DCIM/Camera/IMG_001.jpg", size=2_000_000)]
        with patch.object(LocalInventory, "scan", return_value={}):
            plan = self.engine.compute(remote)
        assert "DCIM/Camera/IMG_001.jpg" in plan.entries


class TestSyncPlan:
    def _make_plan(self) -> SyncPlan:
        plan = SyncPlan(remote_root="/sdcard", local_root="/backup")
        plan.entries = {
            "a.jpg": SyncEntry("a.jpg", FileStatus.TO_COPY, make_remote("/sdcard/a.jpg", 100)),
            "b.jpg": SyncEntry("b.jpg", FileStatus.TO_UPDATE, make_remote("/sdcard/b.jpg", 200)),
            "c.jpg": SyncEntry("c.jpg", FileStatus.IDENTICAL, make_remote("/sdcard/c.jpg", 50)),
            "d.jpg": SyncEntry("d.jpg", FileStatus.ORPHAN, local_size=75),
        }
        return plan

    def test_counts(self):
        plan = self._make_plan()
        assert plan.to_copy_count == 1
        assert plan.to_update_count == 1
        assert plan.identical_count == 1
        assert plan.orphan_count == 1

    def test_total_bytes_to_transfer(self):
        plan = self._make_plan()
        assert plan.total_bytes_to_transfer == 300

    def test_by_status(self):
        plan = self._make_plan()
        copies = plan.by_status(FileStatus.TO_COPY)
        assert len(copies) == 1
        assert copies[0].relative_path == "a.jpg"

    def test_transfers_returns_pairs(self):
        plan = self._make_plan()
        transfers = plan.transfers()
        assert len(transfers) == 2
        remotes = [r for r, _ in transfers]
        assert "/sdcard/a.jpg" in remotes
        assert "/sdcard/b.jpg" in remotes

    def test_needs_transfer_property(self):
        e_copy = SyncEntry("a.jpg", FileStatus.TO_COPY)
        e_update = SyncEntry("b.jpg", FileStatus.TO_UPDATE)
        e_identical = SyncEntry("c.jpg", FileStatus.IDENTICAL)
        e_orphan = SyncEntry("d.jpg", FileStatus.ORPHAN)
        assert e_copy.needs_transfer
        assert e_update.needs_transfer
        assert not e_identical.needs_transfer
        assert not e_orphan.needs_transfer


class TestFormatSize:
    @pytest.mark.parametrize("size, expected", [
        (0, "0 o"),
        (512, "512 o"),
        (1024, "1.0 Ko"),
        (1_048_576, "1.0 Mo"),
        (1_073_741_824, "1.0 Go"),
        (1_500_000_000, "1.4 Go"),
    ])
    def test_format_size(self, size, expected):
        assert format_size(size) == expected
