"""
Application TUI principale (Textual).

Ce module définit :class:`AndroidSaveApp`, le point d'entrée de l'interface
graphique en mode terminal. L'interface s'organise en trois zones :

- **En-tête** : informations sur l'appareil connecté.
- **Corps** : deux panneaux (arborescence téléphone / backup local), légende,
  liste des couples de dossiers et log.
- **Pied de page** : barre de progression et raccourcis clavier.

.. seealso::
    - :mod:`android_save.tui.panels` pour les composants d'arborescence.
    - :mod:`android_save.tui.pairs` pour le widget des couples de dossiers.
    - :mod:`android_save.tui.progress` pour la barre de transfert.
    - :mod:`android_save.adb` pour la couche ADB.
    - :mod:`android_save.sync` pour le moteur de comparaison.
    - :mod:`android_save.config` pour la configuration TOML.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, RichLog, Static

from android_save.adb import AdbClient, AdbError, Device, DeviceNotFoundError, PullProgress
from android_save.config import FolderPair
from android_save.sync import FileStatus, SyncEngine, SyncPlan, format_size
from android_save.tui.pairs import FolderPairsPanel, PairStatus
from android_save.tui.panels import STATUS_STYLE, FileTreePanel
from android_save.tui.progress import TransferProgress


class ConfirmScreen(ModalScreen[bool]):
    """Écran modal de confirmation avant le lancement du transfert.

    :param message: Texte de confirmation à afficher.

    Retourne ``True`` si l'utilisateur confirme, ``False`` sinon.
    """

    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    ConfirmScreen > Container {
        width: 70; height: auto;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    ConfirmScreen Label {
        width: 100%; text-align: center; margin-bottom: 1;
    }
    ConfirmScreen Horizontal { align: center middle; height: auto; }
    ConfirmScreen Button { margin: 0 2; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Construit le message et les boutons de confirmation."""
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

    Accepte une liste de :class:`~android_save.config.FolderPair` définissant
    les couples de dossiers à synchroniser. Chaque couple est traité
    séquentiellement lors du transfert.

    :param pairs: Couples de dossiers à synchroniser.
    :param serial: Serial ADB de l'appareil à cibler (optionnel).
    :param adb_client: Instance :class:`~android_save.adb.AdbClient` à utiliser.
    :param copy_only: Si ``True`` (défaut), ne copie que les fichiers absents en local
        et ignore les mises à jour. La touche ``c`` bascule ce mode pendant l'exécution.

    Raccourcis clavier :

    - ``s`` : Lancer la synchronisation de tous les couples.
    - ``r`` : Actualiser l'inventaire du couple courant.
    - ``q`` : Quitter.

    Exemple::

        from android_save.config import FolderPair
        app = AndroidSaveApp(pairs=[
            FolderPair("/sdcard/DCIM", "~/Photos"),
            FolderPair("/sdcard/Documents", "~/Documents"),
        ])
        app.run()
    """

    TITLE = "Android Save"
    SUB_TITLE = "Sauvegarde ADB"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("s", "start_sync", "Synchroniser", show=True),
        Binding("c", "toggle_copy_only", "Copies seules", show=True),
        Binding("r", "refresh_inventory", "Actualiser", show=True),
        Binding("q", "quit", "Quitter", show=True),
    ]

    DEFAULT_CSS = """
    AndroidSaveApp { background: $background; }
    #status_bar {
        height: 1; background: $accent; color: $text; padding: 0 1;
    }
    #main_container { height: 1fr; }
    #panels { width: 1fr; height: 1fr; }
    #legend { height: 1; padding: 0 1; background: $surface; }
    #mode_bar { height: 1; padding: 0 1; }
    #log_panel { height: 8; border-top: solid $accent; }
    FileTreePanel {
        width: 1fr; height: 1fr; border: solid $border; padding: 0 1;
    }
    TransferProgress { height: 4; border-top: solid $accent; }
    """

    def __init__(
        self,
        pairs: list[FolderPair] | None = None,
        serial: str | None = None,
        adb_client: AdbClient | None = None,
        copy_only: bool = True,
        # rétrocompatibilité
        remote_root: str = "/sdcard",
        local_root: str = str(Path.home() / "android_backup"),
    ) -> None:
        """Initialise l'application avec les couples, l'appareil et le mode de copie."""
        super().__init__()
        if pairs:
            self._pairs = pairs
        else:
            self._pairs = [FolderPair(remote=remote_root, local=local_root)]
        self._serial = serial
        self._adb = adb_client or AdbClient()
        self._device: Device | None = None
        self._plans: list[SyncPlan | None] = [None] * len(self._pairs)
        self._current_idx: int = 0
        self._syncing = False
        self._copy_only: bool = copy_only
        self._skip_current: bool = False

    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        """Construit l'interface principale (panneaux, légende, couples, log)."""
        yield Header()
        yield Static("En attente d'un appareil…", id="status_bar")
        with Vertical(id="main_container"):
            with Horizontal(id="panels"):
                yield FileTreePanel(title="Téléphone", id="panel_remote")
                yield FileTreePanel(
                    title=f"Backup → {self._pairs[0].local}", id="panel_local"
                )
            s = STATUS_STYLE
            yield Static(
                f"[{s[FileStatus.TO_COPY]}]+ à copier[/]  "
                f"[{s[FileStatus.TO_UPDATE]}]~ à mettre à jour[/]  "
                f"[{s[FileStatus.IDENTICAL]}]  identique[/]  "
                f"[{s[FileStatus.ORPHAN]}]? orphelin (local seulement)[/]",
                id="legend",
            )
            yield Static("", id="mode_bar", markup=True)
            yield FolderPairsPanel(self._pairs, id="pairs_panel")
            yield RichLog(id="log_panel", max_lines=200, markup=True)
        yield TransferProgress(id="transfer_progress")
        yield Footer()

    def on_mount(self) -> None:
        """Lance la détection de l'appareil au démarrage."""
        if self._copy_only:
            self.query_one("#mode_bar", Static).update(
                "[bold #f1c40f]⚑ Mode : copies seules — les fichiers existants ne seront pas mis à jour[/]"
            )
        self.detect_device()

    # ------------------------------------------------------------------ device

    @work(thread=True)
    def detect_device(self) -> None:
        """Détecte l'appareil Android connecté (tâche arrière-plan).

        Met à jour la barre de statut et lance l'inventaire du premier couple
        si un appareil est trouvé.
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
            self.run_inventory(0)
        except AdbError as exc:
            self._log(f"[red]Erreur ADB : {exc}[/red]")
            self.call_from_thread(
                self.query_one("#status_bar", Static).update,
                f"Aucun appareil détecté ({exc})",
            )
        except Exception as exc:
            self._log(f"[red]Erreur inattendue : {exc}[/red]")

    # ---------------------------------------------------------------- inventory

    @work(thread=True)
    def run_inventory(self, pair_idx: int = 0) -> None:
        """Inventorie les fichiers pour le couple d'index ``pair_idx``.

        Met à jour les panneaux et le :class:`~android_save.tui.pairs.FolderPairsPanel`.

        :param pair_idx: Index du couple à inventorier.
        """
        if not self._device or pair_idx >= len(self._pairs):
            return
        pair = self._pairs[pair_idx]
        self._current_idx = pair_idx
        self._log(f"Inventaire de {pair.remote}…")

        self.call_from_thread(
            lambda: setattr(
                self.query_one("#panel_local", FileTreePanel),
                "border_title",
                f"Backup → {pair.local}",
            )
        )

        try:
            remote_files = self._adb.list_files(self._device, pair.remote)
            self._log(f"{len(remote_files)} fichiers sur le téléphone")

            engine = SyncEngine(pair.remote, pair.local)
            plan = engine.compute(remote_files)
            self._plans[pair_idx] = plan

            n_transfer = plan.to_copy_count + plan.to_update_count
            self.call_from_thread(
                self.query_one("#pairs_panel", FolderPairsPanel).set_status,
                pair_idx,
                PairStatus.PENDING,
                n_transfer,
                0,
            )

            summary = (
                f"[dim]{pair.display}[/]  "
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
        except Exception as exc:
            self._log(f"[red]Erreur inattendue (inventaire) : {exc}[/red]")

    def _refresh_panels(self, plan: SyncPlan) -> None:
        """Met à jour les deux panneaux (thread principal)."""
        self.query_one("#panel_remote", FileTreePanel).load_plan(plan, side="remote")
        self.query_one("#panel_local", FileTreePanel).load_plan(plan, side="local")

    def action_refresh_inventory(self) -> None:
        """Action ``r`` : relance l'inventaire du couple courant."""
        if self._device:
            self.run_inventory(self._current_idx)
        else:
            self.detect_device()

    # ------------------------------------------------------------------ sync

    def on_transfer_progress_skip(self, _message: TransferProgress.Skip) -> None:
        """Interruption du fichier en cours demandée par le bouton Stop."""
        if self._syncing:
            self._skip_current = True
            self._adb.skip_current()

    def action_toggle_copy_only(self) -> None:
        """Action ``c`` : bascule le mode « copies seules » (sans mises à jour)."""
        self._copy_only = not self._copy_only
        if self._copy_only:
            self.query_one("#mode_bar", Static).update(
                "[bold #f1c40f]⚑ Mode : copies seules — les fichiers existants ne seront pas mis à jour[/]"
            )
            self._log("[#f1c40f]Mode copies seules activé[/]")
        else:
            self.query_one("#mode_bar", Static).update("")
            self._log("[dim]Mode copies seules désactivé[/]")

    def action_start_sync(self) -> None:
        """Action ``s`` : calcule le total de tous les couples et demande confirmation."""
        if self._syncing:
            self._log("[yellow]Transfert déjà en cours[/yellow]")
            return

        if self._copy_only:
            total_files = sum(p.to_copy_count for p in self._plans if p is not None)
        else:
            total_files = sum(
                (p.to_copy_count + p.to_update_count)
                for p in self._plans if p is not None
            )
        total_bytes = sum(
            p.bytes_to_transfer(self._copy_only) for p in self._plans if p is not None
        )
        uninventoried = sum(1 for p in self._plans if p is None)

        if uninventoried:
            self._log(
                f"[yellow]{uninventoried} couple(s) non inventorié(s) — "
                "ils seront inventoriés avant transfert[/yellow]"
            )

        if total_files == 0 and uninventoried == 0:
            self._log("[#2ecc71]Tout est déjà à jour[/]")
            return

        parts = [f"{total_files} fichier(s)"]
        if total_bytes:
            parts.append(format_size(total_bytes))
        if uninventoried:
            parts.append(f"+ {uninventoried} couple(s) à inventorier")
        if self._copy_only:
            parts.append("copies seules")
        msg = "Synchroniser " + ", ".join(parts) + " ?"
        self.push_screen(ConfirmScreen(msg), self._on_confirm)

    def _on_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self.sync_all_pairs()

    @work(thread=True)
    def sync_all_pairs(self) -> None:
        """Traite tous les couples séquentiellement (inventaire + transfert).

        Pour chaque couple :

        1. Inventorie si pas encore fait.
        2. Marque le couple ``IN_PROGRESS`` dans :class:`~android_save.tui.pairs.FolderPairsPanel`.
        3. Transfère les fichiers via :meth:`~android_save.adb.AdbClient.pull_batch`.
        4. Marque ``DONE`` ou ``ERROR`` selon le résultat.
        """
        if not self._device:
            return
        self._syncing = True
        try:
            progress_widget = self.query_one("#transfer_progress", TransferProgress)
            pairs_panel = self.query_one("#pairs_panel", FolderPairsPanel)

            for idx, pair in enumerate(self._pairs):
                # --- inventaire si nécessaire ---
                if self._plans[idx] is None:
                    self._log(f"Inventaire de {pair.remote}…")
                    try:
                        remote_files = self._adb.list_files(self._device, pair.remote)
                        engine = SyncEngine(pair.remote, pair.local)
                        self._plans[idx] = engine.compute(remote_files)
                        self.call_from_thread(self._refresh_panels, self._plans[idx])
                    except AdbError as exc:
                        self._log(f"[red]Erreur inventaire {pair.display} : {exc}[/red]")
                        self.call_from_thread(pairs_panel.set_status, idx, PairStatus.ERROR)
                        continue

                plan = self._plans[idx]
                transfers = plan.transfers(copy_only=self._copy_only)
                if not transfers:
                    self._log(f"[dim]{pair.display} — déjà à jour[/]")
                    self.call_from_thread(
                        pairs_panel.set_status, idx, PairStatus.DONE,
                        0, 0,
                    )
                    continue

                # Index remote_path → mtime pour préserver les timestamps après copie
                remote_to_mtime: dict[str, float] = {
                    e.remote_file.path: e.remote_file.mtime
                    for e in plan.entries.values()
                    if e.remote_file and e.needs_transfer
                }

                # --- transfert ---
                self.call_from_thread(
                    pairs_panel.set_status, idx, PairStatus.IN_PROGRESS,
                    len(transfers), 0,
                )
                self.call_from_thread(self._refresh_panels, plan)
                pair_bytes = plan.bytes_to_transfer(self._copy_only)
                self._log(
                    f"[{STATUS_STYLE[FileStatus.TO_COPY]}]▶[/] "
                    f"{pair.display} — {len(transfers)} fichier(s) "
                    f"({format_size(pair_bytes)})"
                )
                self.call_from_thread(progress_widget.reset, pair_bytes)

                errors: list[str] = []
                skipped: int = 0
                cumulative_bytes = 0
                files_done = 0

                def on_progress(p: PullProgress, index: int, _total: int) -> None:
                    nonlocal cumulative_bytes
                    cumulative_bytes += p.bytes_transferred
                    self.call_from_thread(
                        progress_widget.update_transfer,
                        current=index,
                        total=len(transfers),
                        current_file=p.remote_path,
                        cumulative_bytes=cumulative_bytes,
                        file_bytes=p.bytes_transferred,
                    )

                for remote, local, err in self._adb.pull_batch(
                    self._device, transfers, on_progress
                ):
                    if err:
                        if self._skip_current:
                            self._skip_current = False
                            skipped += 1
                            self._log(f"[#f1c40f]⏭ Passé :[/] {Path(remote).name}")
                            try:
                                Path(str(local)).unlink(missing_ok=True)
                            except Exception:
                                pass
                        else:
                            errors.append(str(err))
                            self._log(f"[red]✗[/red] {remote} — {err}")
                    else:
                        files_done += 1
                        # Préserver le timestamp du fichier source (adb pull ne le fait pas)
                        mtime = remote_to_mtime.get(remote)
                        if mtime is not None:
                            try:
                                os.utime(str(local), (mtime, mtime))
                            except OSError:
                                pass

                self.call_from_thread(progress_widget.hide_skip_button)
                status = PairStatus.ERROR if errors else PairStatus.DONE
                self.call_from_thread(
                    pairs_panel.set_status, idx, status, len(transfers), files_done,
                )
                if errors:
                    self._log(
                        f"[red]{pair.display} — {len(errors)} erreur(s)[/red]"
                    )
                else:
                    msg = f"[{STATUS_STYLE[FileStatus.TO_COPY]}]✓[/] {pair.display} — terminé"
                    if skipped:
                        msg += f" ([#f1c40f]{skipped} passé(s)[/])"
                    self._log(msg)
                # invalide le plan pour forcer un ré-inventaire au prochain 'r'
                self._plans[idx] = None

            self._log("[#2ecc71]Synchronisation complète[/]")
        except Exception as exc:
            self._log(f"[red]Erreur inattendue (synchronisation) : {exc}[/red]")
        finally:
            self._syncing = False
            self._skip_current = False

    # ------------------------------------------------------------------ log

    def _log(self, message: str) -> None:
        """Ajoute un message au log (thread-safe, markup Rich accepté).

        :param message: Message à afficher.
        """
        try:
            self.call_from_thread(
                self.query_one("#log_panel", RichLog).write, message
            )
        except Exception:
            pass
