"""
Point d'entrée de l'application ``android-save``.

Flux de lancement :

1. Lecture de ``backup_dir.toml`` (répertoire courant ou ``~/.config/android_save/``).
2. Lancement de :class:`~android_save.tui.setup.SetupApp` : connexion ADB, sélection
   de la source, liste cochable → génère ``save_android_{serial}_todo.toml``.
3. Lancement de :class:`~android_save.tui.app.AndroidSaveApp` avec le fichier todo.

Mode direct (bypass du setup) : utilisez ``--file`` pour passer un fichier TOML
existant directement à l'interface principale.

Usage::

    android-save                          # flux setup → app (recommandé)
    android-save --file ~/mon_config.toml # bypass setup, fichier direct
    android-save --serial emulator-5554   # forcer un appareil spécifique
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="android-save",
        description="Sauvegarde de fichiers Android via ADB avec interface TUI.",
    )
    parser.add_argument(
        "--file",
        default=None,
        metavar="TOML",
        help="Fichier TOML de configuration (bypass le setup interactif)",
    )
    parser.add_argument(
        "--serial",
        default=None,
        metavar="ID",
        help="Serial ADB de l'appareil à utiliser (optionnel)",
    )
    parser.add_argument(
        "--no-copy-only",
        action="store_true",
        default=False,
        help="Inclure les mises à jour (désactive le mode copies seules activé par défaut)",
    )
    return parser.parse_args()


def main() -> None:
    """Lance l'application android-save.

    :raises SystemExit: Si ADB est introuvable ou si le fichier de config est invalide.
    """
    args = _parse_args()

    try:
        from android_save.adb import AdbClient
        from android_save.config import ConfigError, FolderPair, load_config, read_backup_dir
        from android_save.tui.app import AndroidSaveApp
        from android_save.tui.setup import SetupApp
    except ImportError as exc:
        print(f"Erreur d'import : {exc}", file=sys.stderr)
        print("Installez les dépendances : uv pip install -e '.[dev]'", file=sys.stderr)
        sys.exit(1)

    try:
        AdbClient()._run("version")
    except Exception:
        print("Erreur : 'adb' introuvable. Installez android-tools-adb.", file=sys.stderr)
        sys.exit(1)

    # ---------------------------------------------------------------- mode direct

    if args.file:
        try:
            cfg = load_config(args.file)
        except ConfigError as exc:
            print(f"Erreur de configuration : {exc}", file=sys.stderr)
            sys.exit(1)
        app = AndroidSaveApp(
            pairs=cfg.pairs,
            serial=args.serial or cfg.serial,
            adb_client=AdbClient(),
            copy_only=not args.no_copy_only,
        )
        app.run()
        return

    # ---------------------------------------------------------------- flux setup

    backup_dir = read_backup_dir()
    if backup_dir is None:
        backup_dir = Path.home() / "android_backup"
        print(
            f"backup_dir.toml introuvable — utilisation de {backup_dir}",
            file=sys.stderr,
        )

    setup = SetupApp(backup_dir=backup_dir, serial_hint=args.serial)
    result = setup.run()

    if result is None:
        return  # l'utilisateur a quitté le setup

    todo_path, serial = result

    try:
        cfg = load_config(todo_path)
    except ConfigError as exc:
        print(f"Erreur de configuration (todo) : {exc}", file=sys.stderr)
        sys.exit(1)

    app = AndroidSaveApp(
        pairs=cfg.pairs,
        serial=args.serial or serial,
        adb_client=AdbClient(),
        copy_only=not args.no_copy_only,
    )
    app.run()


if __name__ == "__main__":
    main()
