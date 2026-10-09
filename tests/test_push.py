"""Tests unitaires des modules :mod:`android_save.push` et push dans
:mod:`android_save.adb`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from android_save.adb import AdbClient, AdbError, Device, PushProgress
from android_save.push import PushEngine, PushPlan, PushStatus


@pytest.fixture
def client() -> AdbClient:
    return AdbClient()


@pytest.fixture
def device() -> Device:
    return Device(serial="71991fe3", model="OnePlus 5T", status="device")


# ---------------------------------------------------------------------------
# PushEngine.compute
# ---------------------------------------------------------------------------


class TestPushEngineCompute:
    def _remote(self, path: str, size: int = 100, mtime: float = 1000.0):
        from android_save.adb import RemoteFile
        return RemoteFile(path=path, size=size, mtime=mtime)

    def test_new_local_file_marked_to_push(self, tmp_path):
        (tmp_path / "track.mp3").write_bytes(b"x" * 200)
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([])
        assert plan.to_push_count == 1
        assert plan.entries["track.mp3"].status == PushStatus.TO_PUSH

    def test_identical_file_ignored(self, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"x" * 100)
        mtime = f.stat().st_mtime
        remote = self._remote("/sdcard/Music/track.mp3", size=100, mtime=mtime)
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([remote])
        assert plan.entries["track.mp3"].status == PushStatus.IDENTICAL
        assert plan.identical_count == 1

    def test_size_differs_marks_to_update(self, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"x" * 100)
        remote = self._remote("/sdcard/Music/track.mp3", size=200)
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([remote])
        assert plan.entries["track.mp3"].status == PushStatus.TO_UPDATE

    def test_remote_only_file_detected(self, tmp_path):
        remote = self._remote("/sdcard/Music/old.mp3")
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([remote])
        assert plan.remote_only_count == 1
        assert plan.entries["old.mp3"].status == PushStatus.REMOTE_ONLY

    def test_mtime_tolerance_respected(self, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"x" * 100)
        mtime = f.stat().st_mtime
        remote = self._remote("/sdcard/Music/track.mp3", size=100, mtime=mtime + 1.5)
        engine = PushEngine(str(tmp_path), "/sdcard/Music", mtime_tolerance=2.0)
        plan = engine.compute([remote])
        assert plan.entries["track.mp3"].status == PushStatus.IDENTICAL

    def test_path_traversal_ignored(self, tmp_path):
        from android_save.adb import RemoteFile
        remote = RemoteFile(path="/sdcard/Music/../secret.txt", size=10, mtime=0.0)
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([remote])
        assert not plan.entries

    def test_subdirectory_files(self, tmp_path):
        sub = tmp_path / "album"
        sub.mkdir()
        (sub / "track.mp3").write_bytes(b"x" * 50)
        engine = PushEngine(str(tmp_path), "/sdcard/Music")
        plan = engine.compute([])
        assert "album/track.mp3" in plan.entries


# ---------------------------------------------------------------------------
# PushPlan.transfers
# ---------------------------------------------------------------------------


class TestPushPlanTransfers:
    def _plan_with(self, tmp_path, entries: dict) -> PushPlan:
        plan = PushPlan(local_root=str(tmp_path), remote_root="/sdcard/Music")
        plan.entries = entries
        return plan

    def test_copy_only_excludes_updates(self, tmp_path):
        from android_save.push import PushEntry
        plan = PushPlan(
            local_root=str(tmp_path),
            remote_root="/sdcard/Music",
            entries={
                "a.mp3": PushEntry("a.mp3", PushStatus.TO_PUSH, local_size=10),
                "b.mp3": PushEntry("b.mp3", PushStatus.TO_UPDATE, local_size=20),
            },
        )
        transfers = plan.transfers(copy_only=True)
        assert len(transfers) == 1
        assert transfers[0][0].endswith("a.mp3")

    def test_update_mode_includes_both(self, tmp_path):
        from android_save.push import PushEntry
        plan = PushPlan(
            local_root=str(tmp_path),
            remote_root="/sdcard/Music",
            entries={
                "a.mp3": PushEntry("a.mp3", PushStatus.TO_PUSH, local_size=10),
                "b.mp3": PushEntry("b.mp3", PushStatus.TO_UPDATE, local_size=20),
            },
        )
        transfers = plan.transfers(copy_only=False)
        assert len(transfers) == 2

    def test_remote_path_constructed_correctly(self, tmp_path):
        from android_save.push import PushEntry
        plan = PushPlan(
            local_root=str(tmp_path),
            remote_root="/sdcard/Music",
            entries={"sub/track.mp3": PushEntry("sub/track.mp3", PushStatus.TO_PUSH)},
        )
        transfers = plan.transfers()
        assert transfers[0][1] == "/sdcard/Music/sub/track.mp3"


# ---------------------------------------------------------------------------
# AdbClient.push
# ---------------------------------------------------------------------------


class TestAdbPush:
    def test_push_calls_mkdir_and_push(self, client, device, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"hello")
        run_calls = []

        def fake_run(*args, **kwargs):
            run_calls.append(args)
            return ""

        with patch.object(client, "_run", side_effect=fake_run):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.communicate.return_value = ("", "")
                proc.returncode = 0
                mock_popen.return_value = proc

                client.push(device, str(f), "/sdcard/Music/track.mp3")

        assert any("mkdir" in " ".join(str(a) for a in call) for call in run_calls)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "push" in cmd
        assert "/sdcard/Music/track.mp3" in cmd

    def test_push_raises_on_adb_error(self, client, device, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"hello")

        with patch.object(client, "_run", return_value=""):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.communicate.return_value = ("", "error: device not found")
                proc.returncode = 1
                mock_popen.return_value = proc

                with pytest.raises(AdbError):
                    client.push(device, str(f), "/sdcard/Music/track.mp3")

    def test_push_calls_on_progress(self, client, device, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"x" * 42)
        progress_calls = []

        with patch.object(client, "_run", return_value=""):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.communicate.return_value = ("", "")
                proc.returncode = 0
                mock_popen.return_value = proc

                client.push(device, str(f), "/sdcard/Music/track.mp3",
                            on_progress=progress_calls.append)

        assert len(progress_calls) == 1
        p = progress_calls[0]
        assert isinstance(p, PushProgress)
        assert p.total_bytes == 42


# ---------------------------------------------------------------------------
# AdbClient.push_batch
# ---------------------------------------------------------------------------


class TestAdbPushBatch:
    def test_yields_results_for_each_file(self, client, device, tmp_path):
        files = []
        for name in ("a.mp3", "b.mp3"):
            f = tmp_path / name
            f.write_bytes(b"x")
            files.append((str(f), f"/sdcard/Music/{name}"))

        with patch.object(client, "push") as mock_push:
            results = list(client.push_batch(device, files))

        assert len(results) == 2
        assert all(err is None for _, _, err in results)

    def test_error_on_one_does_not_stop_others(self, client, device, tmp_path):
        files = [(str(tmp_path / "a.mp3"), "/sdcard/a.mp3"),
                 (str(tmp_path / "b.mp3"), "/sdcard/b.mp3")]

        call_count = 0

        def fake_push(dev, local, remote, on_progress=None):
            nonlocal call_count
            call_count += 1
            if "a.mp3" in str(local):
                raise AdbError("device offline")

        with patch.object(client, "push", side_effect=fake_push):
            results = list(client.push_batch(device, files))

        assert call_count == 2
        errors = [err for _, _, err in results]
        assert errors[0] is not None
        assert errors[1] is None
