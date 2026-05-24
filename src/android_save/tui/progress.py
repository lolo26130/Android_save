"""
Widget de progression du transfert de fichiers.

Ce module fournit :class:`TransferProgress`, un widget Textual affichant
la progression globale du transfert en cours avec :

- Une barre de progression animée avec volume cumulé / total et vitesses à droite.
- Le nom du fichier en cours de transfert.
- Le compteur de fichiers et volume transféré.

.. seealso::
    :class:`android_save.tui.app.AndroidSaveApp` qui appelle
    :meth:`TransferProgress.update_transfer`.
"""

from __future__ import annotations

import time

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, ProgressBar, Static

from android_save.sync import format_size


def _fmt_speed(bytes_per_sec: float) -> str:
    """Formate une vitesse en octets/s en chaîne lisible.

    :param bytes_per_sec: Vitesse en octets par seconde.
    :return: Chaîne formatée (ex: ``"4.2 Mo/s"``).
    """
    return f"{format_size(int(bytes_per_sec))}/s"


class TransferProgress(Widget):
    """Barre de progression du transfert ADB avec affichage des vitesses.

    .. attribute:: Skip

        Message émis quand l'utilisateur appuie sur le bouton **Stop**.
        L'application doit l'écouter pour interrompre le fichier en cours.

    Affiche trois lignes :

    1. Barre de progression + ``X / total`` + vitesses (à droite).
    2. Nom du fichier en cours de transfert.
    3. Compteur ``fichier X / N`` et volume transféré cumulé.

    :Example:

    .. code-block:: python

        progress = TransferProgress()
        progress.reset(total_bytes=31_000_000_000)
        progress.update_transfer(
            current=5,
            total=100,
            current_file="/sdcard/DCIM/photo.jpg",
            cumulative_bytes=52_428_800,
            file_bytes=10_485_760,
        )
    """

    class Skip(Message):
        """Demande d'interrompre le fichier en cours de transfert."""

    DEFAULT_CSS = """
    TransferProgress {
        height: auto;
        padding: 0 1;
        background: $panel;
    }
    TransferProgress #progress_row {
        height: 3;
    }
    TransferProgress #progress_bar {
        width: 1fr;
        height: 3;
    }
    TransferProgress #total_size {
        width: auto;
        content-align: right middle;
        color: $text-muted;
        padding: 0 1;
    }
    TransferProgress #speed_stats {
        width: auto;
        min-width: 36;
        content-align: right middle;
        color: $text-muted;
        padding: 0 0 0 1;
    }
    TransferProgress #btn_skip {
        width: auto;
        min-width: 10;
        margin: 0 0 0 1;
        display: none;
    }
    TransferProgress #current_file {
        height: 1;
        color: $text-muted;
        overflow: hidden;
    }
    TransferProgress #transfer_stats {
        height: 1;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="progress_row"):
            yield ProgressBar(total=100, show_eta=False, id="progress_bar")
            yield Static("", id="total_size")
            yield Static("", id="speed_stats")
            yield Button("Stop", id="btn_skip", variant="warning")
        yield Static("", id="current_file")
        yield Static("", id="transfer_stats")

    @on(Button.Pressed, "#btn_skip")
    def on_skip_pressed(self) -> None:
        """Émet :class:`Skip` pour demander l'interruption du fichier en cours."""
        self.post_message(self.Skip())

    def reset(self, total_bytes: int = 0) -> None:
        """Remet la barre à zéro et affiche le volume total à transférer.

        :param total_bytes: Volume total à transférer (affiché à droite de la barre).
        """
        self._transfer_start: float = 0.0
        self._prev_update_time: float = 0.0
        self._total_bytes = total_bytes
        self.query_one("#progress_bar", ProgressBar).progress = 0
        self.query_one("#total_size", Static).update(
            f"[dim]0 o / {format_size(total_bytes)}[/]" if total_bytes else ""
        )
        self.query_one("#speed_stats", Static).update("")
        self.query_one("#current_file", Static).update("")
        self.query_one("#transfer_stats", Static).update("")
        self.query_one("#btn_skip", Button).display = True

    def hide_skip_button(self) -> None:
        """Masque le bouton Stop (appelé en fin de transfert)."""
        self.query_one("#btn_skip", Button).display = False

    def update_transfer(
        self,
        current: int,
        total: int,
        current_file: str = "",
        cumulative_bytes: int = 0,
        file_bytes: int = 0,
    ) -> None:
        """Met à jour l'affichage de la progression et des vitesses.

        :param current: Index du fichier venant d'être transféré (base 1).
        :param total: Nombre total de fichiers à transférer.
        :param current_file: Chemin du fichier venant d'être transféré.
        :param cumulative_bytes: Volume total cumulé transféré depuis le début.
        :param file_bytes: Taille du fichier venant d'être transféré.
        """
        now = time.monotonic()

        if not hasattr(self, "_transfer_start") or self._transfer_start == 0.0:
            self._transfer_start = now
            self._prev_update_time = now

        bar = self.query_one("#progress_bar", ProgressBar)
        bar.total = total or 1
        bar.progress = current

        elapsed_total = now - self._transfer_start
        elapsed_file = now - self._prev_update_time

        avg_speed = cumulative_bytes / elapsed_total if elapsed_total > 0 else 0.0
        file_speed = file_bytes / elapsed_file if elapsed_file > 0 else 0.0

        self._prev_update_time = now

        if getattr(self, "_total_bytes", 0):
            self.query_one("#total_size", Static).update(
                f"[dim]{format_size(cumulative_bytes)} / {format_size(self._total_bytes)}[/]"
            )

        self.query_one("#speed_stats", Static).update(
            f"[dim]fichier:[/] {_fmt_speed(file_speed)}  "
            f"[dim]moy.:[/] {_fmt_speed(avg_speed)}"
        )
        self.query_one("#current_file", Static).update(current_file)

        if total > 0:
            self.query_one("#transfer_stats", Static).update(
                f"Fichier {current} / {total}"
                f"  —  {format_size(cumulative_bytes)} transférés"
            )
        else:
            self.query_one("#transfer_stats", Static).update("")
