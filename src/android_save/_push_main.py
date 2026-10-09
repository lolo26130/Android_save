"""
Point d'entrée de la commande ``android-push``.

Pousse un répertoire local vers un appareil Android via ADB en mode
synchronisation : seuls les fichiers absents (ou modifiés avec ``--update``)
sont transférés.

Usage::

    android-push <source> <destination> [--serial ID] [--dry-run] [--update]

Exemples::

    android-push ~/Music /sdcard/Music
    android-push ~/Music /sdcard/Music --dry-run
    android-push ~/Music /sdcard/Music --serial 71991fe3 --update
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="android-push",
        description="Pousse un répertoire local vers Android via ADB (synchronisation).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  android-push ~/Music /sdcard/Music\n"
            "  android-push ~/Music /sdcard/Music --dry-run\n"
            "  android-push ~/Music /sdcard/Music --serial 71991fe3 --update\n"
        ),
    )
    parser.add_argument("source", help="Répertoire local source")
    parser.add_argument("destination", help="Chemin distant cible (ex: /sdcard/Music)")
    parser.add_argument(
        "--serial", default=None, metavar="ID", help="Serial ADB de l'appareil"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulation sans copie réelle"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Mettre à jour les fichiers modifiés (par défaut : copies seules)",
    )
    return parser.parse_args()


def main() -> None:
    """Lance la commande android-push.

    :raises SystemExit: Si l'appareil est introuvable ou la source invalide.
    """
    args = _parse_args()

    try:
        from android_save.adb import AdbClient, AdbError
        from android_save.push import PushEngine
        from android_save.sync import LocalInventory, format_size
    except ImportError as exc:
        print(f"Erreur d'import : {exc}", file=sys.stderr)
        sys.exit(1)

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print(f"Erreur : '{source}' n'est pas un répertoire.", file=sys.stderr)
        sys.exit(1)

    try:
        client = AdbClient()
        device = client.get_device(args.serial)
    except Exception as exc:
        print(f"Erreur ADB : {exc}", file=sys.stderr)
        sys.exit(1)

    mode = "dry-run" if args.dry_run else ("copies + mises à jour" if args.update else "copies seules")
    print(f"Appareil     : {device.model} ({device.serial})")
    print(f"Source       : {source}")
    print(f"Destination  : {args.destination}")
    print(f"Mode         : {mode}")
    print()

    print("Inventaire local…", end="  ", flush=True)
    local_count = len(LocalInventory(str(source)).scan())
    print(f"{local_count} fichier(s)")

    print("Inventaire distant…", end="  ", flush=True)
    try:
        remote_files = client.list_files(device, args.destination)
    except Exception:
        remote_files = []
    print(f"{len(remote_files)} fichier(s)")
    print()

    engine = PushEngine(local_root=str(source), remote_root=args.destination)
    plan = engine.compute(remote_files)

    print("Plan :")
    print(f"  {plan.to_push_count} fichier(s) à envoyer")
    if args.update:
        print(f"  {plan.to_update_count} fichier(s) à mettre à jour")
    elif plan.to_update_count:
        print(f"  {plan.to_update_count} fichier(s) modifié(s) ignoré(s) (utilisez --update)")
    print(f"  {plan.identical_count} identique(s) ignoré(s)")
    if plan.remote_only_count:
        print(f"  {plan.remote_only_count} présent(s) sur l'appareil seulement")
    print()

    transfers = plan.transfers(copy_only=not args.update)

    if not transfers:
        print("Rien à faire.")
        return

    total = len(transfers)
    ok = err = 0
    for i, (local_path, remote_path) in enumerate(transfers, 1):
        size_str = ""
        lp = Path(local_path)
        if lp.exists():
            size_str = f"  ({format_size(lp.stat().st_size)})"
        print(f"[{i}/{total}] → {remote_path}{size_str}")
        if args.dry_run:
            ok += 1
            continue
        try:
            client.push(device, local_path, remote_path)
            ok += 1
        except Exception as exc:
            print(f"  ERREUR : {exc}", file=sys.stderr)
            err += 1

    print()
    if args.dry_run:
        print(f"Simulation : {ok} fichier(s) seraient envoyés.")
    else:
        print(f"Terminé : {ok} envoyé(s), {err} erreur(s).")


if __name__ == "__main__":
    main()
