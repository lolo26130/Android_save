"""
Point d'entrée de l'application ``android-save``.

Analyse les arguments de la ligne de commande et lance l'interface TUI
:class:`~android_save.tui.app.AndroidSaveApp`.

Usage::

    android-save [OPTIONS]

    Options :
      --remote CHEMIN   Répertoire source sur le téléphone (défaut: /sdcard)
      --local CHEMIN    Répertoire de backup local (défaut: ~/android_backup)
      --serial ID       Forcer un appareil spécifique par son serial ADB

    Exemples ::

        android-save
        android-save --remote /sdcard/DCIM --local ~/photos_backup
        android-save --serial emulator-5554
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
        "--remote",
        default="/sdcard",
        metavar="CHEMIN",
        help="Répertoire source sur le téléphone (défaut: /sdcard)",
    )
    parser.add_argument(
        "--local",
        default=str(Path.home() / "android_backup"),
        metavar="CHEMIN",
        help="Répertoire de backup local (défaut: ~/android_backup)",
    )
    parser.add_argument(
        "--serial",
        default=None,
        metavar="ID",
        help="Serial ADB de l'appareil à utiliser (optionnel)",
    )
    return parser.parse_args()


def main() -> None:
    """Lance l'application android-save.

    Parse les arguments, instancie :class:`~android_save.adb.AdbClient`
    et :class:`~android_save.tui.app.AndroidSaveApp`, puis démarre la boucle
    événementielle Textual.

    :raises SystemExit: Si ADB n'est pas disponible sur le système.
    """
    args = _parse_args()

    try:
        from android_save.adb import AdbClient, AdbError
        from android_save.tui.app import AndroidSaveApp
    except ImportError as exc:
        print(f"Erreur d'import : {exc}", file=sys.stderr)
        print("Installez les dépendances : uv sync", file=sys.stderr)
        sys.exit(1)

    try:
        adb = AdbClient()
        adb._run("version")
    except Exception:
        print("Erreur : 'adb' introuvable. Installez android-tools-adb.", file=sys.stderr)
        sys.exit(1)

    app = AndroidSaveApp(
        remote_root=args.remote,
        local_root=args.local,
        adb_client=AdbClient(),
    )
    app.run()


if __name__ == "__main__":
    main()
