"""
Moteur de synchronisation : comparaison et plan de copie.

Ce module calcule les différences entre l'inventaire du téléphone et le
dossier de backup local, puis produit un :class:`SyncPlan` décrivant les
actions à effectuer.

.. seealso::
    - :mod:`android_save.adb` pour l'inventaire des fichiers distants.
    - :mod:`android_save.tui.app` pour l'affichage du plan.

Exemple d'utilisation::

    from android_save.sync import SyncEngine, SyncPlan

    engine = SyncEngine(remote_root="/sdcard", local_root="/backup")
    plan = engine.compute(remote_files, local_files)
    print(f"{plan.to_copy_count} fichiers à copier")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator

from android_save.adb import RemoteFile


class FileStatus(Enum):
    """État d'un fichier dans le plan de synchronisation.

    .. list-table::
       :header-rows: 1

       * - Valeur
         - Signification
       * - ``TO_COPY``
         - Absent en local, doit être copié.
       * - ``TO_UPDATE``
         - Présent des deux côtés mais modifié (taille ou date différente).
       * - ``IDENTICAL``
         - Identique côté téléphone et backup.
       * - ``ORPHAN``
         - Présent en local seulement (fichier supprimé du téléphone).
    """

    TO_COPY = auto()
    TO_UPDATE = auto()
    IDENTICAL = auto()
    ORPHAN = auto()


@dataclass
class SyncEntry:
    """Un fichier dans le plan de synchronisation.

    :param relative_path: Chemin relatif par rapport à la racine (commune aux deux côtés).
    :param status: État du fichier (:class:`FileStatus`).
    :param remote_file: Métadonnées côté téléphone (``None`` pour les orphelins).
    :param local_size: Taille en octets côté backup local (``None`` si absent).
    :param local_mtime: Timestamp de modification côté backup (``None`` si absent).
    """

    relative_path: str
    status: FileStatus
    remote_file: RemoteFile | None = None
    local_size: int | None = None
    local_mtime: float | None = None

    @property
    def remote_path(self) -> str | None:
        """Chemin absolu sur le téléphone ou ``None``."""
        return self.remote_file.path if self.remote_file else None

    @property
    def remote_size(self) -> int | None:
        """Taille sur le téléphone ou ``None``."""
        return self.remote_file.size if self.remote_file else None

    @property
    def needs_transfer(self) -> bool:
        """``True`` si ce fichier doit être transféré (copie ou mise à jour)."""
        return self.status in (FileStatus.TO_COPY, FileStatus.TO_UPDATE)


@dataclass
class SyncPlan:
    """Résultat de la comparaison entre téléphone et backup.

    :param entries: Ensemble des entrées indexées par chemin relatif.
    :param remote_root: Racine sur le téléphone (ex: ``/sdcard``).
    :param local_root: Racine du backup local.

    .. note::
        Accéder aux entrées par statut via :meth:`by_status` ou les propriétés
        de comptage.
    """

    entries: dict[str, SyncEntry] = field(default_factory=dict)
    remote_root: str = "/sdcard"
    local_root: str = ""

    @property
    def to_copy_count(self) -> int:
        """Nombre de fichiers à copier (absents en local)."""
        return sum(1 for e in self.entries.values() if e.status == FileStatus.TO_COPY)

    @property
    def to_update_count(self) -> int:
        """Nombre de fichiers à mettre à jour (modifiés)."""
        return sum(1 for e in self.entries.values() if e.status == FileStatus.TO_UPDATE)

    @property
    def identical_count(self) -> int:
        """Nombre de fichiers identiques (aucune action requise)."""
        return sum(1 for e in self.entries.values() if e.status == FileStatus.IDENTICAL)

    @property
    def orphan_count(self) -> int:
        """Nombre de fichiers orphelins (présents en local seulement)."""
        return sum(1 for e in self.entries.values() if e.status == FileStatus.ORPHAN)

    @property
    def total_bytes_to_transfer(self) -> int:
        """Volume total en octets à transférer (copies + mises à jour)."""
        return sum(
            e.remote_size or 0
            for e in self.entries.values()
            if e.needs_transfer and e.remote_size is not None
        )

    def by_status(self, status: FileStatus) -> list[SyncEntry]:
        """Retourne les entrées filtrées par statut.

        :param status: Statut à filtrer (:class:`FileStatus`).
        :return: Liste triée par chemin relatif.
        """
        return sorted(
            [e for e in self.entries.values() if e.status == status],
            key=lambda e: e.relative_path,
        )

    def transfers(self) -> list[tuple[str, str]]:
        """Retourne la liste des transferts à effectuer sous forme ``(remote, local)``.

        :return: Paires ``(chemin_absolu_remote, chemin_absolu_local)`` pour
            tous les fichiers nécessitant un transfert.
        """
        result = []
        local_root = Path(self.local_root)
        for entry in self.entries.values():
            if entry.needs_transfer and entry.remote_file:
                local_dest = str(local_root / entry.relative_path)
                result.append((entry.remote_file.path, local_dest))
        return sorted(result, key=lambda t: t[0])


@dataclass
class LocalInventory:
    """Inventaire du système de fichiers local.

    :param root: Répertoire racine du backup.

    Exemple::

        inv = LocalInventory("/backup/android")
        files = inv.scan()
    """

    root: str

    def scan(self) -> dict[str, tuple[int, float]]:
        """Scanne récursivement le répertoire local.

        :return: Dictionnaire ``{chemin_relatif: (taille, mtime)}``.
        """
        result: dict[str, tuple[int, float]] = {}
        root = Path(self.root)
        if not root.exists():
            return result
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = Path(dirpath) / fname
                try:
                    stat = full.stat()
                    rel = str(full.relative_to(root))
                    result[rel] = (stat.st_size, stat.st_mtime)
                except OSError:
                    continue
        return result


class SyncEngine:
    """Moteur de calcul du plan de synchronisation.

    Compare l'inventaire distant (:class:`~android_save.adb.RemoteFile`) avec
    l'inventaire local (:class:`LocalInventory`) et produit un :class:`SyncPlan`.

    :param remote_root: Répertoire racine sur le téléphone (ex: ``/sdcard``).
    :param local_root: Répertoire de backup sur le PC.
    :param mtime_tolerance: Écart en secondes toléré sur les timestamps (défaut: 2s).

    Exemple::

        engine = SyncEngine("/sdcard", "/backup/mon_telephone")
        plan = engine.compute(remote_files)
        for entry in plan.by_status(FileStatus.TO_COPY):
            print(entry.relative_path)
    """

    def __init__(
        self,
        remote_root: str,
        local_root: str,
        mtime_tolerance: float = 2.0,
    ) -> None:
        self.remote_root = remote_root.rstrip("/")
        self.local_root = local_root
        self.mtime_tolerance = mtime_tolerance

    def _relative(self, remote_path: str) -> str:
        """Calcule le chemin relatif d'un fichier distant par rapport à ``remote_root``.

        :param remote_path: Chemin absolu sur le téléphone.
        :return: Chemin relatif (séparateur: ``/``).
        """
        if remote_path.startswith(self.remote_root + "/"):
            return remote_path[len(self.remote_root) + 1:]
        return remote_path.lstrip("/")

    def _is_same(
        self,
        remote: RemoteFile,
        local_size: int,
        local_mtime: float,
    ) -> bool:
        """Détermine si un fichier distant et local sont identiques.

        Compare d'abord la taille (rapide), puis le timestamp avec une
        tolérance pour les systèmes de fichiers arrondissant les dates.

        :param remote: Fichier distant.
        :param local_size: Taille locale en octets.
        :param local_mtime: Timestamp local.
        :return: ``True`` si les fichiers sont considérés identiques.
        """
        if remote.size != local_size:
            return False
        return abs(remote.mtime - local_mtime) <= self.mtime_tolerance

    def compute(self, remote_files: list[RemoteFile]) -> SyncPlan:
        """Calcule le plan de synchronisation complet.

        :param remote_files: Liste des fichiers sur le téléphone (via
            :meth:`~android_save.adb.AdbClient.list_files`).
        :return: :class:`SyncPlan` prêt à afficher et exécuter.

        .. note::
            Les fichiers dont le chemin relatif contient ``..`` sont ignorés
            pour des raisons de sécurité.
        """
        local_inv = LocalInventory(self.local_root).scan()
        plan = SyncPlan(remote_root=self.remote_root, local_root=self.local_root)

        seen_rel: set[str] = set()

        for rf in remote_files:
            rel = self._relative(rf.path)
            if ".." in rel.split("/"):
                continue
            seen_rel.add(rel)

            if rel in local_inv:
                local_size, local_mtime = local_inv[rel]
                if self._is_same(rf, local_size, local_mtime):
                    status = FileStatus.IDENTICAL
                else:
                    status = FileStatus.TO_UPDATE
                plan.entries[rel] = SyncEntry(
                    relative_path=rel,
                    status=status,
                    remote_file=rf,
                    local_size=local_size,
                    local_mtime=local_mtime,
                )
            else:
                plan.entries[rel] = SyncEntry(
                    relative_path=rel,
                    status=FileStatus.TO_COPY,
                    remote_file=rf,
                )

        for rel, (local_size, local_mtime) in local_inv.items():
            if rel not in seen_rel:
                plan.entries[rel] = SyncEntry(
                    relative_path=rel,
                    status=FileStatus.ORPHAN,
                    local_size=local_size,
                    local_mtime=local_mtime,
                )

        return plan


def format_size(size_bytes: int) -> str:
    """Formate une taille en octets en chaîne lisible.

    :param size_bytes: Taille en octets.
    :return: Chaîne formatée (ex: ``"1.4 Go"``).

    Exemple::

        >>> format_size(1_500_000_000)
        '1.4 Go'
        >>> format_size(512)
        '512 o'
    """
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}" if unit == "o" else f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} Po"
