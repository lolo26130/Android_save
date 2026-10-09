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

Exemple de fichier TOML::

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

        cfg = load_config("~/mon_config.toml")
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


def read_backup_dir(search_dirs: list[Path] | None = None) -> Path | None:
    """Cherche ``backup_dir.toml`` et retourne le répertoire de backup configuré.

    Cherche dans l'ordre : répertoire courant, puis ``~/.config/android_save/``.

    :param search_dirs: Répertoires de recherche (remplace les défauts si fourni).
    :return: Chemin du répertoire de backup, ou ``None`` si introuvable.

    Exemple::

        backup_dir = read_backup_dir() or Path.home() / "android_backup"
    """
    if search_dirs is None:
        search_dirs = [
            Path.cwd(),
            Path.home() / ".config" / "android_save",
        ]
    for d in search_dirs:
        p = d / "backup_dir.toml"
        if p.exists():
            try:
                with open(p, "rb") as fh:
                    data = tomllib.load(fh)
                raw = data.get("backup_dir", "").strip()
                if raw:
                    return Path(raw).expanduser()
            except (tomllib.TOMLDecodeError, KeyError, OSError):
                pass
    return None


def write_config(
    path: Path,
    pairs: list[FolderPair],
    serial: str | None = None,
) -> None:
    """Écrit un fichier de configuration TOML.

    Crée les répertoires parents si nécessaire.

    :param path: Chemin de destination du fichier ``.toml``.
    :param pairs: Liste des couples de dossiers à écrire.
    :param serial: Serial ADB de l'appareil (optionnel, section ``[device]``).

    Exemple::

        write_config(
            Path("~/android_backup/save_android_ABC123_todo.toml"),
            pairs=[FolderPair("/sdcard/DCIM", "~/android_backup/DCIM", "Photos")],
            serial="ABC123",
        )
    """
    lines: list[str] = []
    if serial:
        lines.append("[device]")
        lines.append(f'serial = "{serial}"')
        lines.append("")
    for pair in pairs:
        lines.append("[[sync]]")
        lines.append(f'remote = "{pair.remote}"')
        lines.append(f'local  = "{pair.local}"')
        if pair.label:
            lines.append(f'label  = "{pair.label}"')
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
