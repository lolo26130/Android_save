"""Tests unitaires du module :mod:`android_save.config`."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from android_save.config import (
    Config,
    ConfigError,
    FolderPair,
    default_config_path,
    load_config,
    read_backup_dir,
    write_config,
)


# ------------------------------------------------------------------ helpers

def write_toml(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "android_save.toml"
    f.write_text(textwrap.dedent(content))
    return f


# ------------------------------------------------------------------ FolderPair

class TestFolderPair:
    def test_display_uses_label_when_set(self):
        pair = FolderPair(remote="/sdcard/DCIM", local="/backup/Photos", label="Photos")
        assert pair.display == "Photos"

    def test_display_falls_back_to_remote_local(self):
        pair = FolderPair(remote="/sdcard/DCIM", local="/backup/Photos")
        assert pair.display == "/sdcard/DCIM → /backup/Photos"

    def test_display_empty_label_falls_back(self):
        pair = FolderPair(remote="/sdcard/DCIM", local="/backup", label="")
        assert "→" in pair.display

    def test_frozen(self):
        pair = FolderPair(remote="/sdcard", local="/backup")
        with pytest.raises(Exception):
            pair.remote = "/other"  # type: ignore[misc]


# ------------------------------------------------------------------ load_config

class TestLoadConfig:
    def test_basic_single_pair(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard/DCIM"
            local  = "/backup/Photos"
        """)
        cfg = load_config(f)
        assert len(cfg.pairs) == 1
        assert cfg.pairs[0].remote == "/sdcard/DCIM"
        assert cfg.pairs[0].local == "/backup/Photos"
        assert cfg.pairs[0].label == ""

    def test_multiple_pairs(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard/DCIM"
            local  = "/backup/Photos"

            [[sync]]
            remote = "/sdcard/WhatsApp"
            local  = "/backup/WhatsApp"
        """)
        cfg = load_config(f)
        assert len(cfg.pairs) == 2
        assert cfg.pairs[1].remote == "/sdcard/WhatsApp"

    def test_label_parsed(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard/DCIM"
            local  = "/backup/Photos"
            label  = "Mes Photos"
        """)
        cfg = load_config(f)
        assert cfg.pairs[0].label == "Mes Photos"

    def test_serial_parsed(self, tmp_path):
        f = write_toml(tmp_path, """
            [device]
            serial = "ABC123"

            [[sync]]
            remote = "/sdcard"
            local  = "/backup"
        """)
        cfg = load_config(f)
        assert cfg.serial == "ABC123"

    def test_no_serial_is_none(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard"
            local  = "/backup"
        """)
        cfg = load_config(f)
        assert cfg.serial is None

    def test_local_expanduser(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard/DCIM"
            local  = "~/Photos"
        """)
        cfg = load_config(f)
        assert not cfg.pairs[0].local.startswith("~")
        assert cfg.pairs[0].local == str(Path("~/Photos").expanduser())

    def test_accepts_path_object(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard"
            local  = "/backup"
        """)
        cfg = load_config(Path(f))
        assert len(cfg.pairs) == 1

    def test_accepts_string_path(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard"
            local  = "/backup"
        """)
        cfg = load_config(str(f))
        assert len(cfg.pairs) == 1


# ------------------------------------------------------------------ ConfigError

class TestConfigError:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(ConfigError, match="introuvable"):
            load_config(tmp_path / "inexistant.toml")

    def test_invalid_toml(self, tmp_path):
        f = tmp_path / "bad.toml"
        f.write_text("[[[ not valid toml")
        with pytest.raises(ConfigError, match="TOML invalide"):
            load_config(f)

    def test_empty_sync_list(self, tmp_path):
        f = write_toml(tmp_path, "# pas de sync")
        with pytest.raises(ConfigError, match="Aucun couple"):
            load_config(f)

    def test_missing_remote(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            local = "/backup"
        """)
        with pytest.raises(ConfigError):
            load_config(f)

    def test_missing_local(self, tmp_path):
        f = write_toml(tmp_path, """
            [[sync]]
            remote = "/sdcard"
        """)
        with pytest.raises(ConfigError):
            load_config(f)


# ------------------------------------------------------------------ read_backup_dir

class TestReadBackupDir:
    def test_finds_backup_dir_toml_in_search_dir(self, tmp_path):
        (tmp_path / "backup_dir.toml").write_text('backup_dir = "/my/backup"', encoding="utf-8")
        result = read_backup_dir(search_dirs=[tmp_path])
        assert result == Path("/my/backup")

    def test_expanduser_applied(self, tmp_path):
        (tmp_path / "backup_dir.toml").write_text('backup_dir = "~/backup"', encoding="utf-8")
        result = read_backup_dir(search_dirs=[tmp_path])
        assert result is not None
        assert not str(result).startswith("~")

    def test_returns_none_when_not_found(self, tmp_path):
        result = read_backup_dir(search_dirs=[tmp_path])
        assert result is None

    def test_first_match_wins(self, tmp_path):
        d1 = tmp_path / "d1"; d1.mkdir()
        d2 = tmp_path / "d2"; d2.mkdir()
        (d1 / "backup_dir.toml").write_text('backup_dir = "/first"', encoding="utf-8")
        (d2 / "backup_dir.toml").write_text('backup_dir = "/second"', encoding="utf-8")
        result = read_backup_dir(search_dirs=[d1, d2])
        assert result == Path("/first")

    def test_ignores_invalid_toml(self, tmp_path):
        (tmp_path / "backup_dir.toml").write_text("[[[ invalid", encoding="utf-8")
        result = read_backup_dir(search_dirs=[tmp_path])
        assert result is None


# ------------------------------------------------------------------ write_config

class TestWriteConfig:
    def test_writes_sync_entries(self, tmp_path):
        pairs = [FolderPair("/sdcard/DCIM", "/backup/DCIM", "Photos")]
        out = tmp_path / "out.toml"
        write_config(out, pairs)
        cfg = load_config(out)
        assert len(cfg.pairs) == 1
        assert cfg.pairs[0].remote == "/sdcard/DCIM"
        assert cfg.pairs[0].local == "/backup/DCIM"
        assert cfg.pairs[0].label == "Photos"

    def test_writes_serial_when_given(self, tmp_path):
        pairs = [FolderPair("/sdcard/DCIM", "/backup/DCIM")]
        out = tmp_path / "out.toml"
        write_config(out, pairs, serial="ABC123")
        cfg = load_config(out)
        assert cfg.serial == "ABC123"

    def test_no_serial_section_when_absent(self, tmp_path):
        pairs = [FolderPair("/sdcard/DCIM", "/backup/DCIM")]
        out = tmp_path / "out.toml"
        write_config(out, pairs)
        assert "[device]" not in out.read_text()

    def test_multiple_pairs_roundtrip(self, tmp_path):
        pairs = [
            FolderPair("/sdcard/DCIM", "/backup/DCIM", "Photos"),
            FolderPair("/sdcard/WhatsApp", "/backup/WhatsApp", ""),
        ]
        out = tmp_path / "out.toml"
        write_config(out, pairs)
        cfg = load_config(out)
        assert len(cfg.pairs) == 2
        assert cfg.pairs[1].remote == "/sdcard/WhatsApp"

    def test_creates_parent_directories(self, tmp_path):
        pairs = [FolderPair("/sdcard/DCIM", "/backup/DCIM")]
        out = tmp_path / "subdir" / "deep" / "out.toml"
        write_config(out, pairs)
        assert out.exists()

    def test_overwrites_existing_file(self, tmp_path):
        out = tmp_path / "out.toml"
        pairs_v1 = [FolderPair("/sdcard/DCIM", "/backup/DCIM")]
        write_config(out, pairs_v1)
        pairs_v2 = [FolderPair("/sdcard/WhatsApp", "/backup/WhatsApp")]
        write_config(out, pairs_v2)
        cfg = load_config(out)
        assert cfg.pairs[0].remote == "/sdcard/WhatsApp"


# ------------------------------------------------------------------ misc

class TestDefaultConfigPath:
    def test_returns_path_object(self):
        p = default_config_path()
        assert isinstance(p, Path)

    def test_contains_android_save(self):
        p = default_config_path()
        assert "android_save" in str(p)

    def test_is_toml(self):
        p = default_config_path()
        assert p.suffix == ".toml"
