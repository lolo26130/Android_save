"""
Chargement de la configuration depuis un fichier TOML.

Format attendu::

    [device]
    serial = "ABC123"   # optionnel

    [[sync]]
    remote = "/sdcard/DCIM"
    local  = "~/Photos_Android"
    label  = "Photos"   # optionnel

    [[sync]]
    remote = "/sdcard/Documents"
    local  = "~/Documents_Android"

.. seealso::
    :func:`load_config` pour charger le fichier.
    :class:`FolderPair` pour la structure d'un couple de dossiers.

Exemple de fichier ``android_save.toml``::

    [[sync]]
    remote = "/sdcard/DCIM"
    local  = "~/backup/Photos"
    label  = "Photos"

    [[sync]]
    remote = "/sdcard/WhatsApp"
    local  = "~/backup/WhatsApp"

    [[sync]]
    remote = "/sdcard/Documents"
    local  = "~/backup/Documents"
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FolderPair:
    """Un couple de dossiers source (téléphone) / destination (PC).

    :param remote: Chemin absolu sur le téléphone (ex: ``/sdcard/DCIM``).
    :param local: Chemin absolu sur le PC (déjà résolu avec ``expanduser``).
    :param label: Nom court affiché dans l'interface (optionnel).
    """

    remote: str
    local: str
    label: str = ""

    @property
    def display(self) -> str:
        """Libellé affiché dans l'interface.

        :return: :attr:`label` si défini, sinon ``remote → local``.
        """
        return self.label if self.label else f"{self.remote} → {self.local}"


@dataclass
class Config:
    """Configuration complète chargée depuis le fichier TOML.

    :param pairs: Liste des couples de dossiers à synchroniser.
    :param serial: Identifiant ADB de l'appareil à cibler (optionnel).
    """

    pairs: list[FolderPair] = field(default_factory=list)
    serial: str | None = None


class ConfigError(ValueError):
    """Erreur de configuration (fichier invalide ou manquant)."""


def load_config(path: str | Path) -> Config:
    """Charge et valide un fichier de configuration TOML.

    :param path: Chemin vers le fichier ``.toml``.
    :raises ConfigError: Si le fichier est illisible ou ne contient aucun couple.
    :return: Instance :class:`Config` prête à l'emploi.

    Exemple::

        cfg = load_config("~/android_save.toml")
        for pair in cfg.pairs:
            print(pair.remote, "→", pair.local)
    """
    path = Path(path).expanduser()
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"Fichier introuvable : {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Fichier TOML invalide : {exc}") from exc

    serial = data.get("device", {}).get("serial") or None

    pairs: list[FolderPair] = []
    for item in data.get("sync", []):
        remote = item.get("remote", "").strip()
        local_raw = item.get("local", "").strip()
        if not remote or not local_raw:
            raise ConfigError("Chaque entrée [sync] doit avoir 'remote' et 'local'")
        pairs.append(FolderPair(
            remote=remote,
            local=str(Path(local_raw).expanduser()),
            label=item.get("label", ""),
        ))

    if not pairs:
        raise ConfigError("Aucun couple [sync] trouvé dans le fichier de configuration")

    return Config(pairs=pairs, serial=serial)


def default_config_path() -> Path:
    """Retourne le chemin par défaut du fichier de configuration.

    :return: ``~/.config/android_save/android_save.toml``.
    """
    return Path.home() / ".config" / "android_save" / "android_save.toml"
