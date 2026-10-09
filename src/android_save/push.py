"""
Moteur de synchronisation pour le push local → Android.

Ce module calcule les différences entre un répertoire local et un répertoire
distant sur l'appareil, puis produit un :class:`PushPlan` décrivant les
fichiers à envoyer.

C'est le symétrique de :mod:`android_save.sync` (qui gère le pull Android → PC).

.. seealso::
    - :mod:`android_save.adb` pour les méthodes :meth:`~android_save.adb.AdbClient.push`
      et :meth:`~android_save.adb.AdbClient.push_batch`.
    - :mod:`android_save.sync` pour le moteur de synchronisation en sens inverse.

Exemple d'utilisation::

    from android_save.adb import AdbClient
    from android_save.push import PushEngine

    client = AdbClient()
    device = client.get_device()
    remote_files = client.list_files(device, "/sdcard/Music")

    engine = PushEngine(local_root="/backup/Music", remote_root="/sdcard/Music")
    plan = engine.compute(remote_files)
    print(f"{plan.to_push_count} fichier(s) à envoyer")

    for local, remote, err in client.push_batch(device, plan.transfers()):
        print("OK" if not err else f"ERREUR: {err}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from android_save.adb import RemoteFile
from android_save.sync import LocalInventory


class PushStatus(Enum):
    """État d'un fichier dans le plan de push.

    .. list-table::
       :header-rows: 1

       * - Valeur
         - Signification
       * - ``TO_PUSH``
         - Absent sur l'appareil, doit être envoyé.
       * - ``TO_UPDATE``
         - Présent des deux côtés mais différent (taille ou date).
       * - ``IDENTICAL``
         - Identique côté PC et téléphone.
       * - ``REMOTE_ONLY``
         - Présent sur l'appareil seulement (absent en local).
    """

    TO_PUSH = auto()
    TO_UPDATE = auto()
    IDENTICAL = auto()
    REMOTE_ONLY = auto()


@dataclass
class PushEntry:
    """Un fichier dans le plan de push.

    :param relative_path: Chemin relatif par rapport à la racine (commune aux deux côtés).
    :param status: État du fichier (:class:`PushStatus`).
    :param local_size: Taille en octets côté PC (``None`` si absent).
    :param local_mtime: Timestamp côté PC (``None`` si absent).
    :param remote_size: Taille en octets sur l'appareil (``None`` si absent).
    :param remote_mtime: Timestamp sur l'appareil (``None`` si absent).
    """

    relative_path: str
    status: PushStatus
    local_size: int | None = None
    local_mtime: float | None = None
    remote_size: int | None = None
    remote_mtime: float | None = None

    @property
    def needs_transfer(self) -> bool:
        """``True`` si ce fichier doit être envoyé (push ou mise à jour)."""
        return self.status in (PushStatus.TO_PUSH, PushStatus.TO_UPDATE)


@dataclass
class PushPlan:
    """Résultat de la comparaison entre le PC et l'appareil pour un push.

    :param entries: Ensemble des entrées indexées par chemin relatif.
    :param local_root: Répertoire source sur le PC.
    :param remote_root: Répertoire cible sur l'appareil.
    """

    entries: dict[str, PushEntry] = field(default_factory=dict)
    local_root: str = ""
    remote_root: str = "/sdcard"

    @property
    def to_push_count(self) -> int:
        """Nombre de fichiers absents sur l'appareil (à envoyer)."""
        return sum(1 for e in self.entries.values() if e.status == PushStatus.TO_PUSH)

    @property
    def to_update_count(self) -> int:
        """Nombre de fichiers à mettre à jour (présents mais différents)."""
        return sum(1 for e in self.entries.values() if e.status == PushStatus.TO_UPDATE)

    @property
    def identical_count(self) -> int:
        """Nombre de fichiers identiques (aucune action requise)."""
        return sum(1 for e in self.entries.values() if e.status == PushStatus.IDENTICAL)

    @property
    def remote_only_count(self) -> int:
        """Nombre de fichiers présents sur l'appareil seulement."""
        return sum(1 for e in self.entries.values() if e.status == PushStatus.REMOTE_ONLY)

    def transfers(self, copy_only: bool = True) -> list[tuple[str, str]]:
        """Retourne la liste des transferts à effectuer sous forme ``(local, remote)``.

        :param copy_only: Si ``True`` (défaut), seuls les fichiers absents sur
            l'appareil sont inclus. Si ``False``, les mises à jour sont incluses.
        :return: Paires ``(chemin_absolu_local, chemin_absolu_remote)`` triées.
        """
        statuses = {PushStatus.TO_PUSH} if copy_only else {PushStatus.TO_PUSH, PushStatus.TO_UPDATE}
        local_root = Path(self.local_root)
        remote_base = self.remote_root.rstrip("/")
        return sorted(
            [
                (str(local_root / e.relative_path), f"{remote_base}/{e.relative_path}")
                for e in self.entries.values()
                if e.status in statuses
            ],
            key=lambda t: t[0],
        )


class PushEngine:
    """Moteur de calcul du plan de push local → Android.

    Compare l'inventaire local avec l'inventaire distant
    (:class:`~android_save.adb.RemoteFile`) et produit un :class:`PushPlan`.

    :param local_root: Répertoire source sur le PC.
    :param remote_root: Répertoire cible sur l'appareil (ex: ``/sdcard/Music``).
    :param mtime_tolerance: Écart en secondes toléré sur les timestamps (défaut: 2s).

    Exemple::

        engine = PushEngine("/backup/Music", "/sdcard/Music")
        plan = engine.compute(remote_files)
        for local, remote in plan.transfers():
            print(local, "→", remote)
    """

    def __init__(
        self,
        local_root: str,
        remote_root: str,
        mtime_tolerance: float = 2.0,
    ) -> None:
        self.local_root = local_root
        self.remote_root = remote_root.rstrip("/")
        self.mtime_tolerance = mtime_tolerance

    def _relative(self, remote_path: str) -> str:
        """Calcule le chemin relatif d'un fichier distant par rapport à ``remote_root``."""
        if remote_path.startswith(self.remote_root + "/"):
            return remote_path[len(self.remote_root) + 1:]
        return remote_path.lstrip("/")

    def _is_same(self, local_size: int, local_mtime: float, remote: RemoteFile) -> bool:
        """Détermine si un fichier local et distant sont identiques."""
        if local_size != remote.size:
            return False
        return abs(local_mtime - remote.mtime) <= self.mtime_tolerance

    def compute(self, remote_files: list[RemoteFile]) -> PushPlan:
        """Calcule le plan de push complet.

        :param remote_files: Liste des fichiers sur l'appareil (via
            :meth:`~android_save.adb.AdbClient.list_files`). Passer ``[]``
            si le répertoire distant n'existe pas encore.
        :return: :class:`PushPlan` prêt à exécuter.
        """
        local_inv = LocalInventory(self.local_root).scan()
        plan = PushPlan(local_root=self.local_root, remote_root=self.remote_root)

        remote_by_rel: dict[str, RemoteFile] = {}
        for rf in remote_files:
            rel = self._relative(rf.path)
            if ".." not in rel.split("/"):
                remote_by_rel[rel] = rf

        for rel, (local_size, local_mtime) in local_inv.items():
            if rel in remote_by_rel:
                rf = remote_by_rel[rel]
                status = PushStatus.IDENTICAL if self._is_same(local_size, local_mtime, rf) else PushStatus.TO_UPDATE
                plan.entries[rel] = PushEntry(
                    relative_path=rel,
                    status=status,
                    local_size=local_size,
                    local_mtime=local_mtime,
                    remote_size=rf.size,
                    remote_mtime=rf.mtime,
                )
            else:
                plan.entries[rel] = PushEntry(
                    relative_path=rel,
                    status=PushStatus.TO_PUSH,
                    local_size=local_size,
                    local_mtime=local_mtime,
                )

        for rel, rf in remote_by_rel.items():
            if rel not in local_inv:
                plan.entries[rel] = PushEntry(
                    relative_path=rel,
                    status=PushStatus.REMOTE_ONLY,
                    remote_size=rf.size,
                    remote_mtime=rf.mtime,
                )

        return plan
