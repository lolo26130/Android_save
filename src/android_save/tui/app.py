"""
Application TUI principale (Textual).

Ce module définit :class:`AndroidSaveApp`, le point d'entrée de l'interface
graphique en mode terminal. L'interface s'organise en trois zones :

- **En-tête** : informations sur l'appareil connecté.
- **Corps** : deux panneaux (arborescence téléphone / backup local) et log.
- **Pied de page** : barre de progression et raccourcis clavier.

.. seealso::
    - :mod:`android_save.tui.panels` pour les composants d'arborescence.
    - :mod:`android_save.tui.progress` pour la barre de transfert.
    - :mod:`android_save.adb` pour la couche ADB.
    - :mod:`android_save.sync` pour le moteur de comparaison.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
)

from android_save.adb import AdbClient, AdbError, Device, DeviceNotFoundError, PullProgress
from android_save.sync import FileStatus, SyncEngine, SyncPlan, format_size
from android_save.tui.panels import STATUS_STYLE, FileTreePanel
from android_save.tui.progress import TransferProgress


class ConfirmScreen(ModalScreen[bool]):
    """Écran modal de confirmation avant le lancement du transfert.

    :param message: Texte de confirmation à afficher.

    Retourne ``True`` si l'utilisateur confirme, ``False`` sinon.
    """

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > Container {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConfirmScreen Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }
    ConfirmScreen Horizontal {
        align: center middle;
        height: auto;
    }
    ConfirmScreen Button {
        margin: 0 2;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._message)
            with Horizontal():
                yield Button("Lancer", variant="success", id="btn_ok")
                yield Button("Annuler", variant="error", id="btn_cancel")

    @on(Button.Pressed, "#btn_ok")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self) -> None:
        self.dismiss(False)


class AndroidSaveApp(App):
    """Application principale de sauvegarde Android.

    Lance la détection du téléphone, calcule le plan de synchronisation et
    gère le transfert des fichiers avec une interface Textual.

    :param remote_root: Répertoire racine sur le téléphone.
    :param local_root: Répertoire de backup sur le PC.
    :param adb_client: Instance :class:`~android_save.adb.AdbClient` à utiliser.

    Raccourcis clavier :

    - ``s`` : Lancer la synchronisation.
    - ``r`` : Actualiser l'inventaire.
    - ``q`` : Quitter.

    Exemple::

        app = AndroidSaveApp(remote_root="/sdcard", local_root="/backup")
        app.run()
    """

    TITLE = "Android Save"
    SUB_TITLE = "Sauvegarde ADB"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("s", "start_sync", "Synchroniser", show=True),
        Binding("r", "refresh_inventory", "Actualiser", show=True),
        Binding("q", "quit", "Quitter", show=True),
    ]

    DEFAULT_CSS = """
    AndroidSaveApp {
        background: $background;
    }
    #status_bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    #main_container {
        height: 1fr;
    }
    #panels {
        width: 1fr;
        height: 1fr;
    }
    #legend {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #log_panel {
        height: 8;
        border-top: solid $accent;
    }
    FileTreePanel {
        width: 1fr;
        height: 1fr;
        border: solid $border;
        padding: 0 1;
    }
    TransferProgress {
        height: 3;
        border-top: solid $accent;
    }
    """

    def __init__(
        self,
        remote_root: str = "/sdcard",
        local_root: str = str(Path.home() / "android_backup"),
        adb_client: AdbClient | None = None,
    ) -> None:
        super().__init__()
        self.remote_root = remote_root
        self.local_root = local_root
        self._adb = adb_client or AdbClient()
        self._device: Device | None = None
        self._plan: SyncPlan | None = None
        self._syncing = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("En attente d'un appareil…", id="status_bar")
        with Vertical(id="main_container"):
            with Horizontal(id="panels"):
                yield FileTreePanel(title="Téléphone", id="panel_remote")
                yield FileTreePanel(title=f"Backup → {self.local_root}", id="panel_local")
            s = STATUS_STYLE
            yield Static(
                f"[{s[FileStatus.TO_COPY]}]+ à copier[/]  "
                f"[{s[FileStatus.TO_UPDATE]}]~ à mettre à jour[/]  "
                f"[{s[FileStatus.IDENTICAL]}]  identique[/]  "
                f"[{s[FileStatus.ORPHAN]}]? orphelin (local seulement)[/]",
                id="legend",
            )
            yield RichLog(id="log_panel", max_lines=200, markup=True)
        yield TransferProgress(id="transfer_progress")
        yield Footer()

    def on_mount(self) -> None:
        """Lance la détection de l'appareil au démarrage."""
        self.detect_device()

    def on_transfer_progress_follow_file(self, event: TransferProgress.FollowFile) -> None:
        """Centre les deux panneaux sur le fichier venant d'être transféré.

        Calcule le chemin relatif depuis :attr:`remote_root`, puis appelle
        :meth:`~android_save.tui.panels.FileTreePanel.scroll_to_path` sur le
        panneau téléphone. Le panneau local suit via la synchronisation de scroll.

        :param event: Message :class:`~android_save.tui.progress.TransferProgress.FollowFile`.
        """
        remote = event.remote_path
        prefix = self.remote_root.rstrip("/") + "/"
        rel_path = remote[len(prefix):] if remote.startswith(prefix) else remote
        remote_panel = self.query_one("#panel_remote", FileTreePanel)
        remote_panel.scroll_to_path(rel_path)

    def on_file_tree_panel_scrolled(self, event: FileTreePanel.Scrolled) -> None:
        """Synchronise le défilement vertical des deux panneaux.

        Répercute la position ``scroll_y`` du panneau source sur l'autre panneau.
        La tolérance de 0.5 px évite la boucle infinie A→B→A.

        :param event: Message :class:`~android_save.tui.panels.FileTreePanel.Scrolled`.
        """
        for panel in self.query(FileTreePanel):
            if panel is not event.panel and abs(panel.scroll_y - event.y) > 0.5:
                panel.scroll_to(y=event.y, animate=False)

    @work(thread=True)
    def detect_device(self) -> None:
        """Détecte l'appareil Android connecté (tâche arrière-plan).

        Met à jour la barre de statut et lance l'inventaire si un appareil
        est trouvé.
        """
        self._log("Recherche d'un appareil Android…")
        try:
            device = self._adb.wait_for_device(timeout=30)
            self._device = device
            self.call_from_thread(
                self.query_one("#status_bar", Static).update,
                f"Appareil : {device.model} ({device.serial})",
            )
            self._log(f"Appareil trouvé : {device.model}")
            self.run_inventory()
        except DeviceNotFoundError as exc:
            self._log(f"[red]Erreur : {exc}[/red]")
            self.call_from_thread(
                self.query_one("#status_bar", Static).update,
                f"Aucun appareil détecté ({exc})",
            )

    @work(thread=True)
    def run_inventory(self) -> None:
        """Inventorie les fichiers du téléphone et calcule le plan de sync.

        Lance la comparaison via :class:`~android_save.sync.SyncEngine` et
        met à jour les deux panneaux.
        """
        if not self._device:
            return
        self._log(f"Inventaire de {self.remote_root}…")
        try:
            remote_files = self._adb.list_files(self._device, self.remote_root)
            self._log(f"{len(remote_files)} fichiers trouvés sur le téléphone")

            engine = SyncEngine(self.remote_root, self.local_root)
            plan = engine.compute(remote_files)
            self._plan = plan

            summary = (
                f"[{STATUS_STYLE[FileStatus.TO_COPY]}]{plan.to_copy_count} à copier[/]  "
                f"[{STATUS_STYLE[FileStatus.TO_UPDATE]}]{plan.to_update_count} à mettre à jour[/]  "
                f"[{STATUS_STYLE[FileStatus.IDENTICAL]}]{plan.identical_count} identiques[/]  "
                f"[{STATUS_STYLE[FileStatus.ORPHAN]}]{plan.orphan_count} orphelins[/]  "
                f"— {format_size(plan.total_bytes_to_transfer)} à transférer"
            )
            self._log(summary)

            self.call_from_thread(self._refresh_panels, plan)
        except AdbError as exc:
            self._log(f"[red]Erreur ADB : {exc}[/red]")

    def _refresh_panels(self, plan: SyncPlan) -> None:
        """Met à jour les deux panneaux avec le plan calculé (thread principal)."""
        remote_panel = self.query_one("#panel_remote", FileTreePanel)
        local_panel = self.query_one("#panel_local", FileTreePanel)
        remote_panel.load_plan(plan, side="remote")
        local_panel.load_plan(plan, side="local")

    def action_refresh_inventory(self) -> None:
        """Action ``r`` : relance l'inventaire complet."""
        if self._device:
            self.run_inventory()
        else:
            self.detect_device()

    def action_start_sync(self) -> None:
        """Action ``s`` : demande confirmation puis lance le transfert."""
        if self._syncing:
            self._log("[yellow]Transfert déjà en cours[/yellow]")
            return
        if not self._plan:
            self._log("[yellow]Aucun plan disponible — lancez d'abord un inventaire[/yellow]")
            return
        n = self._plan.to_copy_count + self._plan.to_update_count
        size = format_size(self._plan.total_bytes_to_transfer)
        if n == 0:
            self._log("[green]Tout est déjà à jour[/green]")
            return
        msg = f"Transférer {n} fichier(s) ({size}) ?"
        self.push_screen(ConfirmScreen(msg), self._on_confirm)

    def _on_confirm(self, confirmed: bool) -> None:
        """Callback après confirmation : lance ou annule le transfert."""
        if confirmed:
            self.start_transfer()

    @work(thread=True)
    def start_transfer(self) -> None:
        """Exécute le transfert des fichiers (tâche arrière-plan).

        Appelle :meth:`~android_save.adb.AdbClient.pull_batch` et met à jour
        la barre de progression en temps réel.
        """
        if not self._device or not self._plan:
            return
        self._syncing = True
        transfers = self._plan.transfers()
        total = len(transfers)
        progress_widget = self.query_one("#transfer_progress", TransferProgress)

        self._log(f"Démarrage : {total} fichier(s) à transférer")
        self.call_from_thread(progress_widget.reset)

        errors: list[str] = []
        cumulative_bytes = 0

        def on_progress(p: PullProgress, index: int, _total: int) -> None:
            nonlocal cumulative_bytes
            cumulative_bytes += p.bytes_transferred
            self.call_from_thread(
                progress_widget.update_transfer,
                current=index,
                total=total,
                current_file=p.remote_path,
                cumulative_bytes=cumulative_bytes,
                file_bytes=p.bytes_transferred,
            )

        for remote, local, err in self._adb.pull_batch(
            self._device, transfers, on_progress
        ):
            if err:
                errors.append(f"{remote}: {err}")
                self._log(f"[red]Erreur : {remote} — {err}[/red]")
            else:
                self._log(f"[green]✓[/green] {remote}")

        self._syncing = False
        if errors:
            self._log(f"[red]Terminé avec {len(errors)} erreur(s)[/red]")
        else:
            self._log("[green]Synchronisation terminée avec succès[/green]")
            self.call_from_thread(self.run_inventory)

    def _log(self, message: str) -> None:
        """Ajoute un message au panneau de log (thread-safe).

        :param message: Message à afficher (markup Rich accepté).
        """
        try:
            log_widget = self.query_one("#log_panel", RichLog)
            self.call_from_thread(log_widget.write, message)
        except Exception:
            pass
