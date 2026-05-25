"""
Interface de configuration préliminaire d'android-save.

Ce module fournit :class:`SetupApp`, une application Textual légère qui s'exécute
avant l'interface principale. Elle permet de :

- Choisir la source de la liste de synchronisation :
  *depuis le téléphone* (scan ``/sdcard``) ou *fichier utilisateur*.
- Sélectionner les éléments à inclure dans la sauvegarde via une liste cochable.
- Générer le fichier ``save_android_{serial}_todo.toml`` qui est ensuite passé
  à :class:`~android_save.tui.app.AndroidSaveApp`.

.. seealso::
    :func:`android_save.config.write_config` pour l'écriture des fichiers TOML.
    :meth:`android_save.adb.AdbClient.list_top_dirs` pour le scan du téléphone.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from android_save.adb import AdbClient, AdbError, Device
from android_save.config import FolderPair, load_config, write_config


class SetupApp(App[tuple[Path, str] | None]):
    """Application de configuration préliminaire.

    Se connecte à l'appareil Android, propose deux modes de sélection,
    affiche une liste cochable d'éléments et génère le fichier ``.toml`` de
    travail. Retourne ``(todo_path, serial)`` via :meth:`App.exit` ou ``None``
    si l'utilisateur quitte.

    :param backup_dir: Répertoire de travail lu depuis ``backup_dir.toml``.
    :param serial_hint: Serial ADB à cibler en priorité (optionnel).

    Exemple::

        app = SetupApp(backup_dir=Path("~/android_backup").expanduser())
        result = app.run()   # retourne (todo_path, serial) ou None
    """

    TITLE = "Android Save — Configuration"
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quitter"),
    ]

    DEFAULT_CSS = """
    SetupApp { background: $background; }

    #device_status {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    #mode_section {
        height: auto;
        padding: 1 2;
        border: solid $border;
        margin: 1 0;
    }
    #mode_section Label {
        height: 1;
        margin-bottom: 1;
        color: $text-muted;
    }
    #backup_info {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #scan_status {
        height: 1;
        padding: 0 1;
    }
    #items_label {
        height: 1;
        padding: 1 1 0 1;
    }
    #items_container {
        height: 1fr;
        border: solid $border;
        overflow-y: auto;
        padding: 0 1;
    }
    #items_container Checkbox {
        height: auto;
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #footer_buttons {
        height: 3;
        align: right middle;
        padding: 0 1;
        border-top: solid $border;
    }
    #btn_go {
        min-width: 12;
    }
    """

    def __init__(self, backup_dir: Path, serial_hint: str | None = None) -> None:
        super().__init__()
        self._backup_dir = backup_dir
        self._serial_hint = serial_hint
        self._adb = AdbClient()
        self._device: Device | None = None
        self._current_pairs: list[FolderPair] = []

    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Connexion à l'appareil…", id="device_status")
        with Vertical(id="mode_section"):
            yield Label("Source de la liste :")
            with RadioSet(id="mode_radio"):
                yield RadioButton("Créer la liste depuis le téléphone", value=True)
                yield RadioButton("Utiliser le fichier utilisateur")
        yield Static(
            f"[dim]Répertoire de backup : {self._backup_dir}[/dim]",
            id="backup_info",
            markup=True,
        )
        yield Static("", id="scan_status", markup=True)
        yield Label("Éléments à synchroniser :", id="items_label")
        yield ScrollableContainer(id="items_container")
        with Horizontal(id="footer_buttons"):
            yield Button("Go", id="btn_go", variant="success", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self._connect_device()

    # ------------------------------------------------------------------ device

    @work(thread=True)
    def _connect_device(self) -> None:
        try:
            serial = self._serial_hint
            device = self._adb.get_device(serial) if serial else None
            if device is None:
                device = self._adb.wait_for_device(timeout=30)
            self._device = device
            self.call_from_thread(
                self.query_one("#device_status", Static).update,
                f"Appareil : {device.model} ({device.serial})",
            )
            self.call_from_thread(self._trigger_load)
        except AdbError as exc:
            self.call_from_thread(
                self.query_one("#device_status", Static).update,
                f"[red]Aucun appareil détecté ({exc})[/red]",
            )

    def _trigger_load(self) -> None:
        """Lance le chargement selon le mode radio courant (thread principal)."""
        radio = self.query_one("#mode_radio", RadioSet)
        if radio.pressed_index == 0:
            self._scan_phone()
        else:
            self._load_user_file()

    # ------------------------------------------------------------------- mode

    @on(RadioSet.Changed, "#mode_radio")
    def on_mode_changed(self, _event: RadioSet.Changed) -> None:
        if self._device is None:
            return
        self._trigger_load()

    # ------------------------------------------------------------------ scan

    @work(thread=True)
    def _scan_phone(self) -> None:
        """Scanne /sdcard et crée save_android_{serial}_from_android.toml."""
        if self._device is None:
            return
        serial = self._device.serial

        self.call_from_thread(
            self.query_one("#scan_status", Static).update,
            "[dim]Scan du téléphone en cours…[/dim]",
        )
        self.call_from_thread(
            setattr,
            self.query_one("#btn_go", Button),
            "disabled",
            True,
        )

        try:
            dirs = self._adb.list_top_dirs(self._device, "/sdcard")
        except AdbError as exc:
            self.call_from_thread(
                self.query_one("#scan_status", Static).update,
                f"[red]Erreur scan : {exc}[/red]",
            )
            return

        pairs = [
            FolderPair(
                remote=d,
                local=str(self._backup_dir / Path(d).name),
                label=Path(d).name,
            )
            for d in dirs
        ]
        self._current_pairs = pairs

        from_android_path = self._backup_dir / f"save_android_{serial}_from_android.toml"
        write_config(from_android_path, pairs, serial)

        user_path = self._backup_dir / f"save_android_{serial}_user.toml"
        note = f"  •  [dim]{user_path.name} disponible[/dim]" if user_path.exists() else ""
        self.call_from_thread(
            self.query_one("#scan_status", Static).update,
            f"[dim]{len(pairs)} répertoires trouvés[/dim]{note}",
        )
        self.call_from_thread(self._populate_list, pairs)

    # ---------------------------------------------------------------- user file

    def _load_user_file(self) -> None:
        """Charge save_android_{serial}_user.toml et peuple la liste."""
        if self._device is None:
            return
        serial = self._device.serial
        user_path = self._backup_dir / f"save_android_{serial}_user.toml"

        if not user_path.exists():
            self.query_one("#scan_status", Static).update(
                f"[yellow]{user_path.name} introuvable — "
                "choisissez 'depuis le téléphone' ou créez ce fichier[/yellow]"
            )
            self._current_pairs = []
            self._populate_list([])
            return

        try:
            cfg = load_config(user_path)
            self._current_pairs = cfg.pairs
            self.query_one("#scan_status", Static).update(
                f"[dim]{len(cfg.pairs)} éléments dans {user_path.name}[/dim]"
            )
            self._populate_list(cfg.pairs)
        except Exception as exc:
            self.query_one("#scan_status", Static).update(
                f"[red]Erreur lecture {user_path.name} : {exc}[/red]"
            )
            self._current_pairs = []
            self._populate_list([])

    # ------------------------------------------------------------------- list

    def _populate_list(self, pairs: list[FolderPair]) -> None:
        """Reconstruit la liste cochable (thread principal uniquement).

        Les Checkbox n'ont pas d'ID explicite : remove_children() est asynchrone
        dans Textual, donc les anciens widgets restent dans le DOM au moment du
        mount() suivant — un ID fixe provoquerait un conflit.
        On les retrouve par ordre dans on_go_pressed via query(Checkbox).
        """
        container = self.query_one("#items_container", ScrollableContainer)
        container.remove_children()

        for pair in pairs:
            name = pair.label or Path(pair.remote).name
            text = f"{name}   ({pair.remote}  ->  {pair.local})"
            cb = Checkbox(text, value=True)  # pas d'ID
            cb.compact = True
            container.mount(cb)

        self.query_one("#btn_go", Button).disabled = len(pairs) == 0

    # --------------------------------------------------------------------- go

    @on(Button.Pressed, "#btn_go")
    def on_go_pressed(self) -> None:
        """Crée le fichier todo.toml avec les éléments cochés et quitte."""
        if self._device is None:
            return
        serial = self._device.serial

        container = self.query_one("#items_container", ScrollableContainer)
        checkboxes = list(container.query(Checkbox))
        checked: list[FolderPair] = [
            pair
            for pair, cb in zip(self._current_pairs, checkboxes)
            if cb.value
        ]

        if not checked:
            return

        todo_path = self._backup_dir / f"save_android_{serial}_todo.toml"
        write_config(todo_path, checked, serial)
        self.exit(result=(todo_path, serial))
