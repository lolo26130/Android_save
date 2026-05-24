"""
Wrapper ADB pour la communication avec un appareil Android.

Ce module fournit une interface haut niveau autour de la commande ``adb``.
Il gère la détection de l'appareil, l'inventaire des fichiers et le transfert.

.. note::
    Requiert ``adb`` installé et ``USB debugging`` activé sur le téléphone.

Exemple d'utilisation::

    from android_save.adb import AdbClient

    client = AdbClient()
    device = client.get_device()
    files = client.list_files(device, "/sdcard/DCIM")
    client.pull(device, "/sdcard/DCIM/photo.jpg", "/backup/DCIM/photo.jpg")
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator


@dataclass(frozen=True)
class Device:
    """Représente un appareil Android connecté via ADB.

    :param serial: Identifiant unique de l'appareil (ex: ``emulator-5554``).
    :param model: Nom du modèle récupéré via ``adb shell getprop``.
    :param status: État de la connexion (``device``, ``offline``, ``unauthorized``).
    """

    serial: str
    model: str
    status: str


@dataclass(frozen=True)
class RemoteFile:
    """Représente un fichier sur l'appareil Android.

    :param path: Chemin absolu sur le téléphone (ex: ``/sdcard/DCIM/photo.jpg``).
    :param size: Taille en octets.
    :param mtime: Timestamp UNIX de la dernière modification.
    """

    path: str
    size: int
    mtime: float


@dataclass
class PullProgress:
    """Données de progression d'un transfert en cours.

    :param remote_path: Chemin source sur le téléphone.
    :param local_path: Chemin destination sur le PC.
    :param bytes_transferred: Octets déjà transférés.
    :param total_bytes: Taille totale du fichier.
    """

    remote_path: str
    local_path: str
    bytes_transferred: int = 0
    total_bytes: int = 0

    @property
    def ratio(self) -> float:
        """Ratio de complétion entre 0.0 et 1.0.

        :return: 0.0 si la taille totale est inconnue.
        """
        if self.total_bytes == 0:
            return 0.0
        return self.bytes_transferred / self.total_bytes


class AdbError(Exception):
    """Erreur liée à une commande ADB échouée.

    :param message: Description de l'erreur.
    :param returncode: Code de retour du processus ADB.
    """

    def __init__(self, message: str, returncode: int = -1) -> None:
        super().__init__(message)
        self.returncode = returncode


class DeviceNotFoundError(AdbError):
    """Aucun appareil Android détecté ou plusieurs appareils connectés."""


class AdbClient:
    """Client ADB principal.

    Encapsule les appels à la commande ``adb`` du système. Toutes les opérations
    passent par cette classe.

    :param adb_path: Chemin vers l'exécutable ``adb``. Par défaut: ``adb`` (PATH).
    :param timeout: Délai maximum en secondes pour chaque commande.

    Exemple::

        client = AdbClient()
        devices = client.list_devices()
    """

    def __init__(
        self,
        adb_path: str = "adb",
        timeout: int = 30,
        pull_timeout: int | None = None,
    ) -> None:
        self.adb_path = adb_path
        self.timeout = timeout
        self.pull_timeout = pull_timeout  # None = pas de limite (fichiers volumineux)
        self._current_proc: subprocess.Popen | None = None

    def _run(self, *args: str, timeout: int | None = None) -> str:
        """Exécute une commande ADB et retourne la sortie.

        :param args: Arguments à passer à ``adb``.
        :param timeout: Délai spécifique pour cette commande.
        :raises AdbError: Si la commande retourne un code non nul.
        :return: Sortie standard de la commande.
        """
        cmd = [self.adb_path, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"Timeout sur la commande: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise AdbError(f"adb introuvable: {self.adb_path}") from exc

        if result.returncode != 0:
            raise AdbError(result.stderr.strip(), returncode=result.returncode)
        return result.stdout

    def list_devices(self) -> list[Device]:
        """Liste tous les appareils Android connectés.

        :raises AdbError: Si la commande ``adb devices`` échoue.
        :return: Liste des :class:`Device` disponibles.

        Exemple::

            devices = client.list_devices()
            for d in devices:
                print(d.serial, d.model)
        """
        output = self._run("devices", "-l")
        devices: list[Device] = []
        for line in output.splitlines()[1:]:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            status = parts[1]
            model = "inconnu"
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1].replace("_", " ")
                    break
            devices.append(Device(serial=serial, model=model, status=status))
        return devices

    def get_device(self, serial: str | None = None) -> Device:
        """Retourne l'unique appareil connecté ou celui indiqué par ``serial``.

        :param serial: Identifiant de l'appareil à sélectionner.
        :raises DeviceNotFoundError: Si aucun appareil n'est trouvé ou si plusieurs
            sont présents sans que ``serial`` soit précisé.
        :return: L':class:`Device` sélectionné.
        """
        devices = self.list_devices()
        available = [d for d in devices if d.status == "device"]

        if not available:
            raise DeviceNotFoundError(
                "Aucun appareil Android connecté (USB debugging activé ?)"
            )

        if serial:
            for d in available:
                if d.serial == serial:
                    return d
            raise DeviceNotFoundError(f"Appareil {serial!r} introuvable")

        if len(available) > 1:
            raise DeviceNotFoundError(
                f"{len(available)} appareils connectés — précisez le serial"
            )

        return available[0]

    def list_files(self, device: Device, remote_path: str = "/sdcard") -> list[RemoteFile]:
        """Inventorie récursivement les fichiers d'un répertoire Android.

        Utilise ``adb shell find`` avec le format ``%s %T@ %p`` pour récupérer
        taille, timestamp et chemin en une seule passe.

        :param device: Appareil Android cible.
        :param remote_path: Répertoire racine à parcourir.
        :raises AdbError: En cas d'erreur ADB.
        :return: Liste de :class:`RemoteFile`.

        .. warning::
            Cette opération peut prendre plusieurs secondes pour les bibliothèques
            photo volumineuses.
        """
        cmd = f"find {remote_path} -type f -printf '%s %T@ %p\\n' 2>/dev/null"
        output = self._run("-s", device.serial, "shell", cmd, timeout=120)
        files: list[RemoteFile] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                size_str, mtime_str, *path_parts = line.split(" ")
                path = " ".join(path_parts)
                files.append(
                    RemoteFile(
                        path=path,
                        size=int(size_str),
                        mtime=float(mtime_str),
                    )
                )
            except (ValueError, IndexError):
                continue
        return files

    def skip_current(self) -> None:
        """Interrompt le fichier en cours de transfert (tue le sous-processus).

        Sans effet si aucun transfert n'est actif.
        """
        proc = self._current_proc
        if proc is not None:
            proc.kill()

    def pull(
        self,
        device: Device,
        remote_path: str,
        local_path: str | Path,
        on_progress: Callable[[PullProgress], None] | None = None,
    ) -> None:
        """Transfère un fichier depuis l'appareil vers le PC.

        Crée les répertoires parents si nécessaire. Appelle ``on_progress``
        à la fin du transfert (ADB ne fournit pas de progression intermédiaire).
        Le transfert peut être interrompu via :meth:`skip_current`.

        :param device: Appareil Android source.
        :param remote_path: Chemin du fichier sur le téléphone.
        :param local_path: Destination sur le PC.
        :param on_progress: Callback optionnel appelé en fin de transfert.
        :raises AdbError: Si ``adb pull`` échoue ou est interrompu.

        Exemple::

            def afficher(p):
                print(f"{p.remote_path} → {p.ratio:.0%}")

            client.pull(device, "/sdcard/photo.jpg", "/backup/photo.jpg", afficher)
        """
        local = Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)

        cmd = [self.adb_path, "-s", device.serial, "pull", remote_path, str(local)]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError:
            raise AdbError(f"adb introuvable: {self.adb_path}")

        self._current_proc = proc
        try:
            try:
                _stdout, stderr = proc.communicate(timeout=self.pull_timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise AdbError(
                    f"Timeout ({self.pull_timeout}s) dépassé pour : {remote_path}"
                )
        finally:
            self._current_proc = None

        if proc.returncode != 0:
            raise AdbError(stderr.strip(), returncode=proc.returncode)

        if on_progress and local.exists():
            size = local.stat().st_size
            on_progress(
                PullProgress(
                    remote_path=remote_path,
                    local_path=str(local),
                    bytes_transferred=size,
                    total_bytes=size,
                )
            )

    def pull_batch(
        self,
        device: Device,
        transfers: list[tuple[str, str | Path]],
        on_progress: Callable[[PullProgress, int, int], None] | None = None,
    ) -> Iterator[tuple[str, str | Path, Exception | None]]:
        """Transfère une liste de fichiers un par un.

        Générateur qui yield ``(remote, local, erreur)`` après chaque fichier.
        Une erreur sur un fichier n'interrompt pas les suivants.

        :param device: Appareil Android source.
        :param transfers: Liste de tuples ``(chemin_remote, chemin_local)``.
        :param on_progress: Callback ``(progression, index, total)`` après chaque fichier.
        :return: Itérateur de résultats par fichier.

        Exemple::

            for remote, local, err in client.pull_batch(device, to_copy):
                if err:
                    print(f"Erreur: {remote} — {err}")
        """
        total = len(transfers)
        for index, (remote, local) in enumerate(transfers):
            error: Exception | None = None
            try:
                progress_holder: list[PullProgress] = []

                def _capture(p: PullProgress) -> None:
                    progress_holder.append(p)
                    if on_progress:
                        on_progress(p, index + 1, total)

                self.pull(device, remote, local, _capture)
            except AdbError as exc:
                error = exc
            yield remote, local, error

    def wait_for_device(self, timeout: int = 60) -> Device:
        """Attend qu'un appareil soit connecté, avec délai maximum.

        Interroge ``adb devices`` toutes les 2 secondes jusqu'à ``timeout``.

        :param timeout: Délai d'attente maximum en secondes.
        :raises DeviceNotFoundError: Si aucun appareil n'est détecté dans le délai.
        :return: Le premier :class:`Device` disponible.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return self.get_device()
            except DeviceNotFoundError:
                time.sleep(2)
        raise DeviceNotFoundError(f"Aucun appareil après {timeout}s d'attente")
