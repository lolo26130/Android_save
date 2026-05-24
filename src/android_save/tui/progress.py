"""
Widget de progression du transfert de fichiers.

Ce module fournit :class:`TransferProgress`, un widget Textual affichant
la progression globale du transfert en cours avec :

- Une barre de progression animée avec vitesses à droite.
- Le nom du fichier en cours de transfert.
- Le compteur de fichiers et volume transféré.

.. seealso::
    :class:`android_save.tui.app.AndroidSaveApp` qui appelle
    :meth:`TransferProgress.update_transfer`.
"""

from __future__ import annotations

import time

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
    """Barre de progression du transfert ADB avec affichage des vitesses et suivi.

    Affiche trois lignes :

    1. Barre de progression + vitesses à droite + bouton **Suivi**.
    2. Nom du fichier en cours de transfert.
    3. Compteur ``fichier X / N`` et volume transféré cumulé.

    Quand le bouton **Suivi** est actif, émet :class:`FollowFile` après chaque
    fichier afin que l'application puisse centrer les panneaux sur le fichier
    en cours.

    :Example:

    .. code-block:: python

        progress = TransferProgress()
        progress.update_transfer(
            current=5,
            total=100,
            current_file="/sdcard/DCIM/photo.jpg",
            cumulative_bytes=52_428_800,
            file_bytes=10_485_760,
        )
    """

    class FollowFile(Message):
        """Émis après chaque fichier transféré quand le suivi est actif.

        :param remote_path: Chemin absolu du fichier sur le téléphone.
        """

        def __init__(self, remote_path: str) -> None:
            super().__init__()
            self.remote_path = remote_path

    DEFAULT_CSS = """
    TransferProgress {
        height: 4;
        padding: 0 1;
        background: $panel;
    }
    TransferProgress #progress_row {
        height: 1;
    }
    TransferProgress #progress_bar {
        width: 1fr;
    }
    TransferProgress #speed_stats {
        width: auto;
        min-width: 36;
        content-align: right middle;
        color: $text-muted;
        padding: 0 0 0 1;
    }
    TransferProgress #btn_follow {
        width: auto;
        min-width: 10;
        height: 1;
        border: none;
        padding: 0 1;
        margin: 0 0 0 1;
        background: $surface;
        color: $text-muted;
    }
    TransferProgress #btn_follow.active {
        background: #2ecc71;
        color: $background;
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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._follow_active = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="progress_row"):
            yield ProgressBar(total=100, show_eta=False, id="progress_bar")
            yield Static("", id="speed_stats")
            yield Button("○ Suivi", id="btn_follow")
        yield Static("", id="current_file")
        yield Static("", id="transfer_stats")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Bascule le mode suivi actif/inactif."""
        if event.button.id != "btn_follow":
            return
        self._follow_active = not self._follow_active
        btn = self.query_one("#btn_follow", Button)
        if self._follow_active:
            btn.label = "● Suivi"
            btn.add_class("active")
        else:
            btn.label = "○ Suivi"
            btn.remove_class("active")

    def reset(self) -> None:
        """Remet la barre de progression à zéro et réinitialise les chronomètres."""
        self._transfer_start: float = 0.0
        self._prev_update_time: float = 0.0
        self.query_one("#progress_bar", ProgressBar).progress = 0
        self.query_one("#speed_stats", Static).update("")
        self.query_one("#current_file", Static).update("")
        self.query_one("#transfer_stats", Static).update("")

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

        speed_text = (
            f"[dim]fichier:[/] {_fmt_speed(file_speed)}  "
            f"[dim]moy.:[/] {_fmt_speed(avg_speed)}"
        )
        self.query_one("#speed_stats", Static).update(speed_text)
        self.query_one("#current_file", Static).update(current_file)

        if self._follow_active and current_file:
            self.post_message(self.FollowFile(current_file))

        if total > 0:
            self.query_one("#transfer_stats", Static).update(
                f"Fichier {current} / {total}"
                f"  —  {format_size(cumulative_bytes)} transférés"
            )
        else:
            self.query_one("#transfer_stats", Static).update("")
