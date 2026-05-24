"""
Point d'entrée de l'application ``android-save``.

Analyse les arguments de la ligne de commande et lance l'interface TUI
:class:`~android_save.tui.app.AndroidSaveApp`.

Usage::

    android-save [OPTIONS]

    Options :
      --file TOML       Fichier de configuration TOML (couples remote/local)
      --remote CHEMIN   Répertoire source sur le téléphone (ignoré si --file)
      --local CHEMIN    Répertoire de backup local (ignoré si --file)
      --serial ID       Forcer un appareil spécifique par son serial ADB

    Exemples ::

        android-save --file ~/android_save.toml
        android-save --remote /sdcard/DCIM --local ~/Photos_Android
        android-save --serial emulator-5554 --file ~/android_save.toml

Format du fichier TOML::

    [device]
    serial = "ABC123"   # optionnel

    [[sync]]
    remote = "/sdcard/DCIM"
    local  = "~/Photos_Android"
    label  = "Photos"

    [[sync]]
    remote = "/sdcard/Documents"
    local  = "~/Documents_Android"
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
        help="Fichier de configuration TOML définissant les couples de dossiers",
    )
    parser.add_argument(
        "--remote",
        default="/sdcard",
        metavar="CHEMIN",
        help="Répertoire source sur le téléphone (défaut: /sdcard, ignoré si --file)",
    )
    parser.add_argument(
        "--local",
        default=str(Path.home() / "android_backup"),
        metavar="CHEMIN",
        help="Répertoire de backup local (défaut: ~/android_backup, ignoré si --file)",
    )
    parser.add_argument(
        "--serial",
        default=None,
        metavar="ID",
        help="Serial ADB de l'appareil à utiliser (optionnel)",
    )
    parser.add_argument(
        "--copy-only",
        action="store_true",
        default=False,
        help="Copier uniquement les fichiers absents en local (ignorer les mises à jour)",
    )
    return parser.parse_args()


def main() -> None:
    """Lance l'application android-save.

    Parse les arguments, construit la liste des couples de dossiers depuis
    ``--file`` ou ``--remote``/``--local``, instancie
    :class:`~android_save.tui.app.AndroidSaveApp` et démarre la boucle
    événementielle Textual.

    :raises SystemExit: Si ADB est introuvable ou si le fichier de config est invalide.
    """
    args = _parse_args()

    try:
        from android_save.adb import AdbClient
        from android_save.config import ConfigError, FolderPair, load_config
        from android_save.tui.app import AndroidSaveApp
    except ImportError as exc:
        print(f"Erreur d'import : {exc}", file=sys.stderr)
        print("Installez les dépendances : uv sync", file=sys.stderr)
        sys.exit(1)

    try:
        AdbClient()._run("version")
    except Exception:
        print("Erreur : 'adb' introuvable. Installez android-tools-adb.", file=sys.stderr)
        sys.exit(1)

    # Résolution des couples de dossiers
    serial: str | None = args.serial
    if args.file:
        try:
            cfg = load_config(args.file)
            pairs = cfg.pairs
            serial = serial or cfg.serial
        except ConfigError as exc:
            print(f"Erreur de configuration : {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        pairs = [FolderPair(
            remote=args.remote,
            local=str(Path(args.local).expanduser()),
        )]

    app = AndroidSaveApp(pairs=pairs, serial=serial, adb_client=AdbClient(), copy_only=args.copy_only)
    app.run()


if __name__ == "__main__":
    main()
