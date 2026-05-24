"""Tests unitaires du module :mod:`android_save.adb`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from android_save.adb import (
    AdbClient,
    AdbError,
    Device,
    DeviceNotFoundError,
    PullProgress,
    RemoteFile,
)


@pytest.fixture
def client() -> AdbClient:
    return AdbClient()


class TestListDevices:
    def test_single_device(self, client):
        output = (
            "List of devices attached\n"
            "ABC123\t\tdevice product:coral model:Pixel_4 transport_id:1\n"
        )
        with patch.object(client, "_run", return_value=output):
            devices = client.list_devices()
        assert len(devices) == 1
        assert devices[0].serial == "ABC123"
        assert devices[0].status == "device"
        assert devices[0].model == "Pixel 4"

    def test_no_devices(self, client):
        output = "List of devices attached\n"
        with patch.object(client, "_run", return_value=output):
            devices = client.list_devices()
        assert devices == []

    def test_multiple_devices(self, client):
        output = (
            "List of devices attached\n"
            "ABC123\t\tdevice model:Pixel_4\n"
            "DEF456\t\tdevice model:Samsung_S21\n"
        )
        with patch.object(client, "_run", return_value=output):
            devices = client.list_devices()
        assert len(devices) == 2

    def test_unauthorized_device_excluded_from_available(self, client):
        output = (
            "List of devices attached\n"
            "ABC123\t\tunauthorized\n"
        )
        with patch.object(client, "_run", return_value=output):
            devices = client.list_devices()
        assert devices[0].status == "unauthorized"


class TestGetDevice:
    def test_single_device_returned(self, client):
        device = Device("ABC", "Pixel", "device")
        with patch.object(client, "list_devices", return_value=[device]):
            result = client.get_device()
        assert result.serial == "ABC"

    def test_no_device_raises(self, client):
        with patch.object(client, "list_devices", return_value=[]):
            with pytest.raises(DeviceNotFoundError):
                client.get_device()

    def test_multiple_without_serial_raises(self, client):
        devices = [
            Device("A", "Pixel", "device"),
            Device("B", "Galaxy", "device"),
        ]
        with patch.object(client, "list_devices", return_value=devices):
            with pytest.raises(DeviceNotFoundError, match="2 appareils"):
                client.get_device()

    def test_serial_selects_correct_device(self, client):
        devices = [
            Device("A", "Pixel", "device"),
            Device("B", "Galaxy", "device"),
        ]
        with patch.object(client, "list_devices", return_value=devices):
            result = client.get_device(serial="B")
        assert result.serial == "B"

    def test_serial_not_found_raises(self, client):
        devices = [Device("A", "Pixel", "device")]
        with patch.object(client, "list_devices", return_value=devices):
            with pytest.raises(DeviceNotFoundError):
                client.get_device(serial="Z")


class TestListFiles:
    def test_parses_output_correctly(self, client):
        device = Device("ABC", "Pixel", "device")
        output = (
            "1024 1700000000.000000 /sdcard/DCIM/photo.jpg\n"
            "2048 1700000001.000000 /sdcard/Documents/notes.txt\n"
        )
        with patch.object(client, "_run", return_value=output):
            files = client.list_files(device, "/sdcard")
        assert len(files) == 2
        assert files[0].path == "/sdcard/DCIM/photo.jpg"
        assert files[0].size == 1024
        assert files[0].mtime == pytest.approx(1700000000.0)

    def test_ignores_malformed_lines(self, client):
        device = Device("ABC", "Pixel", "device")
        output = "bad_line\n1024 1700000000.0 /sdcard/file.jpg\n"
        with patch.object(client, "_run", return_value=output):
            files = client.list_files(device, "/sdcard")
        assert len(files) == 1

    def test_handles_spaces_in_filename(self, client):
        device = Device("ABC", "Pixel", "device")
        output = "512 1700000000.0 /sdcard/mes photos/vacances 2023.jpg\n"
        with patch.object(client, "_run", return_value=output):
            files = client.list_files(device, "/sdcard")
        assert files[0].path == "/sdcard/mes photos/vacances 2023.jpg"

    def test_empty_output(self, client):
        device = Device("ABC", "Pixel", "device")
        with patch.object(client, "_run", return_value=""):
            files = client.list_files(device, "/sdcard")
        assert files == []


class TestPull:
    def test_creates_parent_directories(self, client, tmp_path):
        device = Device("ABC", "Pixel", "device")
        dest = tmp_path / "subdir" / "file.jpg"

        with patch.object(client, "_run", return_value=""):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake content")
            client.pull(device, "/sdcard/file.jpg", dest)

        assert dest.parent.exists()

    def test_calls_on_progress_after_transfer(self, client, tmp_path):
        device = Device("ABC", "Pixel", "device")
        dest = tmp_path / "file.jpg"
        dest.write_bytes(b"x" * 100)

        progress_calls = []

        def on_prog(p: PullProgress) -> None:
            progress_calls.append(p)

        with patch.object(client, "_run", return_value=""):
            client.pull(device, "/sdcard/file.jpg", dest, on_prog)

        assert len(progress_calls) == 1
        assert progress_calls[0].bytes_transferred == 100

    def test_adb_error_propagates(self, client, tmp_path):
        device = Device("ABC", "Pixel", "device")
        dest = tmp_path / "file.jpg"
        with patch.object(client, "_run", side_effect=AdbError("permission denied")):
            with pytest.raises(AdbError, match="permission denied"):
                client.pull(device, "/sdcard/file.jpg", dest)


class TestPullBatch:
    def test_yields_results_for_each_file(self, client, tmp_path):
        device = Device("ABC", "Pixel", "device")
        files = [
            ("/sdcard/a.jpg", tmp_path / "a.jpg"),
            ("/sdcard/b.jpg", tmp_path / "b.jpg"),
        ]
        for _, local in files:
            Path(local).write_bytes(b"data")

        with patch.object(client, "_run", return_value=""):
            results = list(client.pull_batch(device, files))

        assert len(results) == 2
        assert all(err is None for _, _, err in results)

    def test_error_does_not_abort_batch(self, client, tmp_path):
        device = Device("ABC", "Pixel", "device")
        files = [
            ("/sdcard/ok.jpg", tmp_path / "ok.jpg"),
            ("/sdcard/fail.jpg", tmp_path / "fail.jpg"),
        ]
        (tmp_path / "ok.jpg").write_bytes(b"data")

        def _run_side(*args, **kwargs):
            if "fail.jpg" in str(args):
                raise AdbError("échec")
            return ""

        with patch.object(client, "_run", side_effect=_run_side):
            results = list(client.pull_batch(device, files))

        errors = [err for _, _, err in results if err is not None]
        assert len(errors) == 1


class TestPullProgress:
    def test_ratio_zero_when_no_total(self):
        p = PullProgress("/sdcard/f", "/backup/f", bytes_transferred=0, total_bytes=0)
        assert p.ratio == 0.0

    def test_ratio_calculation(self):
        p = PullProgress("/sdcard/f", "/backup/f", bytes_transferred=50, total_bytes=200)
        assert p.ratio == pytest.approx(0.25)
