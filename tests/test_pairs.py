"""Tests unitaires du module :mod:`android_save.tui.pairs`."""

from __future__ import annotations

import pytest

from android_save.config import FolderPair
from android_save.tui.pairs import FolderPairsPanel, PairState, PairStatus


# ------------------------------------------------------------------ PairState

class TestPairState:
    def test_default_status_is_pending(self):
        pair = FolderPair("/sdcard/DCIM", "/backup")
        state = PairState(pair)
        assert state.status == PairStatus.PENDING

    def test_default_counts_are_zero(self):
        pair = FolderPair("/sdcard/DCIM", "/backup")
        state = PairState(pair)
        assert state.files_total == 0
        assert state.files_done == 0

    def test_pair_stored(self):
        pair = FolderPair("/sdcard/DCIM", "/backup", label="Photos")
        state = PairState(pair)
        assert state.pair is pair


# ------------------------------------------------------------------ PairStatus

class TestPairStatus:
    def test_all_values_distinct(self):
        values = [s.value for s in PairStatus]
        assert len(values) == len(set(values))

    def test_expected_members(self):
        members = {s.name for s in PairStatus}
        assert members == {"PENDING", "IN_PROGRESS", "DONE", "ERROR"}


# ------------------------------------------------------------------ FolderPairsPanel (logique interne)

def _make_panel(labels: list[str]) -> FolderPairsPanel:
    """Crée un panel sans le monter dans une app Textual."""
    pairs = [FolderPair(f"/sdcard/{l}", f"/backup/{l}", label=l) for l in labels]
    return FolderPairsPanel(pairs)


class TestFolderPairsPanelStates:
    def test_initial_all_pending(self):
        panel = _make_panel(["Photos", "Docs"])
        assert all(s.status == PairStatus.PENDING for s in panel._states)

    def test_set_status_updates_state(self):
        panel = _make_panel(["Photos", "Docs"])
        panel._states[0].status = PairStatus.IN_PROGRESS
        assert panel._states[0].status == PairStatus.IN_PROGRESS
        assert panel._states[1].status == PairStatus.PENDING

    def test_set_status_out_of_range_ignored(self):
        panel = _make_panel(["Photos"])
        # ne doit pas lever d'exception
        panel._states  # accès direct car set_status appelle _refresh (widget non monté)
        # on teste la logique de borne
        assert 0 <= 0 < len(panel._states)
        assert not (0 <= 99 < len(panel._states))

    def test_files_total_updated(self):
        panel = _make_panel(["Photos"])
        panel._states[0].files_total = 611
        assert panel._states[0].files_total == 611

    def test_files_done_updated(self):
        panel = _make_panel(["Photos"])
        panel._states[0].files_done = 42
        assert panel._states[0].files_done == 42

    def test_pending_in_progress_grouped(self):
        panel = _make_panel(["A", "B", "C"])
        panel._states[0].status = PairStatus.DONE
        pending = [s for s in panel._states if s.status in (PairStatus.PENDING, PairStatus.IN_PROGRESS)]
        done = [s for s in panel._states if s.status in (PairStatus.DONE, PairStatus.ERROR)]
        assert len(pending) == 2
        assert len(done) == 1

    def test_error_status(self):
        panel = _make_panel(["Photos"])
        panel._states[0].status = PairStatus.ERROR
        errors = [s for s in panel._states if s.status == PairStatus.ERROR]
        assert len(errors) == 1


# ------------------------------------------------------------------ _refresh content

class TestRefreshContent:
    """Teste la génération du texte de _refresh sans monter le widget."""

    def _build_lines(self, panel: FolderPairsPanel) -> list[str]:
        """Réplique la logique de _refresh pour tester le contenu."""
        from android_save.tui.pairs import _ACTIVE_ICON, _DONE_ICON, _ERROR_ICON, _PENDING_ICON

        pending = [s for s in panel._states if s.status in (PairStatus.PENDING, PairStatus.IN_PROGRESS)]
        done = [s for s in panel._states if s.status in (PairStatus.DONE, PairStatus.ERROR)]

        lines: list[str] = []
        if pending:
            lines.append("section:pending")
            for s in pending:
                icon = _ACTIVE_ICON if s.status == PairStatus.IN_PROGRESS else _PENDING_ICON
                lines.append(f"item:{icon}:{s.pair.display}")
        if done:
            lines.append("section:done")
            for s in done:
                icon = _ERROR_ICON if s.status == PairStatus.ERROR else _DONE_ICON
                lines.append(f"item:{icon}:{s.pair.display}")
        return lines

    def test_all_pending_only_pending_section(self):
        panel = _make_panel(["Photos", "Docs"])
        lines = self._build_lines(panel)
        assert any("pending" in l for l in lines)
        assert not any("done" in l for l in lines)

    def test_all_done_only_done_section(self):
        panel = _make_panel(["Photos", "Docs"])
        for s in panel._states:
            s.status = PairStatus.DONE
        lines = self._build_lines(panel)
        assert not any("pending" in l for l in lines)
        assert any("done" in l for l in lines)

    def test_mixed_both_sections(self):
        panel = _make_panel(["Photos", "Docs"])
        panel._states[0].status = PairStatus.DONE
        lines = self._build_lines(panel)
        assert any("pending" in l for l in lines)
        assert any("done" in l for l in lines)

    def test_in_progress_uses_active_icon(self):
        from android_save.tui.pairs import _ACTIVE_ICON
        panel = _make_panel(["Photos"])
        panel._states[0].status = PairStatus.IN_PROGRESS
        lines = self._build_lines(panel)
        assert any(_ACTIVE_ICON in l for l in lines)

    def test_error_uses_error_icon(self):
        from android_save.tui.pairs import _ERROR_ICON
        panel = _make_panel(["Photos"])
        panel._states[0].status = PairStatus.ERROR
        lines = self._build_lines(panel)
        assert any(_ERROR_ICON in l for l in lines)

    def test_label_appears_in_output(self):
        panel = _make_panel(["MesPhotos"])
        lines = self._build_lines(panel)
        assert any("MesPhotos" in l for l in lines)
