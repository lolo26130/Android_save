"""
Widget affichant l'état des couples de dossiers à synchroniser.

Deux sections colorées sont affichées :

- **À traiter** : couples en attente (blanc) ou en cours (jaune).
- **Traités** : couples terminés (vert dim) ou en erreur (rouge dim).

.. seealso::
    :class:`android_save.config.FolderPair` pour la structure d'un couple.
    :class:`android_save.tui.app.AndroidSaveApp` qui met à jour ce widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from android_save.config import FolderPair


class PairStatus(Enum):
    """État d'un couple de dossiers dans la session de synchronisation.

    .. list-table::
       :header-rows: 1

       * - Valeur
         - Signification
       * - ``PENDING``
         - En attente de traitement.
       * - ``IN_PROGRESS``
         - Inventaire ou transfert en cours.
       * - ``DONE``
         - Transfert terminé avec succès.
       * - ``ERROR``
         - Transfert terminé avec au moins une erreur.
    """

    PENDING = auto()
    IN_PROGRESS = auto()
    DONE = auto()
    ERROR = auto()


@dataclass
class PairState:
    """État courant d'un couple de dossiers.

    :param pair: Le couple source/destination.
    :param status: Statut courant (:class:`PairStatus`).
    :param files_total: Nombre total de fichiers à transférer (0 = non inventorié).
    :param files_done: Nombre de fichiers transférés avec succès.
    """

    pair: FolderPair
    status: PairStatus = PairStatus.PENDING
    files_total: int = 0
    files_done: int = 0


_PENDING_ICON = "[dim]○[/]"
_ACTIVE_ICON = "[bold #f1c40f]▶[/]"
_DONE_ICON = "[#2ecc71]✓[/]"
_ERROR_ICON = "[red]✗[/]"


class FolderPairsPanel(Widget):
    """Widget affichant les couples de dossiers et leur statut.

    :param pairs: Liste des :class:`~android_save.config.FolderPair` à afficher.

    Utilisation::

        panel = FolderPairsPanel(pairs)
        panel.set_status(0, PairStatus.IN_PROGRESS)
        panel.set_status(0, PairStatus.DONE, files_total=611, files_done=611)
    """

    DEFAULT_CSS = """
    FolderPairsPanel {
        height: auto;
        max-height: 10;
        border-top: solid $accent;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, pairs: list[FolderPair], **kwargs) -> None:
        super().__init__(**kwargs)
        self._states: list[PairState] = [PairState(p) for p in pairs]

    def compose(self) -> ComposeResult:
        yield Static("", id="pairs_content", markup=True)

    def on_mount(self) -> None:
        self._refresh()

    def set_status(
        self,
        index: int,
        status: PairStatus,
        files_total: int = 0,
        files_done: int = 0,
    ) -> None:
        """Met à jour le statut d'un couple et rafraîchit l'affichage.

        :param index: Index du couple dans la liste (base 0).
        :param status: Nouveau statut (:class:`PairStatus`).
        :param files_total: Nombre total de fichiers (optionnel).
        :param files_done: Nombre de fichiers déjà transférés (optionnel).
        """
        if 0 <= index < len(self._states):
            s = self._states[index]
            s.status = status
            if files_total:
                s.files_total = files_total
            if files_done:
                s.files_done = files_done
            self._refresh()

    def _refresh(self) -> None:
        """Reconstruit le texte affiché."""
        pending = [s for s in self._states if s.status in (PairStatus.PENDING, PairStatus.IN_PROGRESS)]
        done = [s for s in self._states if s.status in (PairStatus.DONE, PairStatus.ERROR)]

        lines: list[str] = []

        if pending:
            lines.append("[dim]À traiter :[/]")
            for state in pending:
                if state.status == PairStatus.IN_PROGRESS:
                    icon = _ACTIVE_ICON
                    color = "#f1c40f"
                else:
                    icon = _PENDING_ICON
                    color = "white"
                suffix = f"  [dim]({state.files_total} fichiers)[/]" if state.files_total else ""
                lines.append(f"  {icon} [{color}]{state.pair.display}[/]{suffix}")

        if done:
            lines.append("[dim]Traités :[/]")
            for state in done:
                if state.status == PairStatus.ERROR:
                    icon = _ERROR_ICON
                    color = "dim red"
                else:
                    icon = _DONE_ICON
                    color = "dim #2ecc71"
                suffix = (
                    f"  [dim]{state.files_done}/{state.files_total} fichiers[/]"
                    if state.files_total else ""
                )
                lines.append(f"  {icon} [{color}]{state.pair.display}[/]{suffix}")

        self.query_one("#pairs_content", Static).update("\n".join(lines))
