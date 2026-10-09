# android-save

Sauvegarde de fichiers Android vers le PC (et envoi PC → Android) via **ADB** (USB debugging), avec une interface TUI interactive inspirée de FreeFileSync.

> FreeFileSync ne supporte pas MTP, et NFS/SSHFS est lent — `android-save` contourne les deux en passant par `adb pull` directement.

---

## Fonctionnalités

- **Vue deux panneaux** : téléphone à gauche, backup local à droite, avec code couleur par statut
- **Multi-dossiers** : l'écran de configuration scanne le téléphone et génère la liste des dossiers — décochez ceux que vous ne voulez pas sauvegarder
- **Copie incrémentale** : seuls les fichiers nouveaux ou modifiés sont transférés (comparaison taille + timestamp)
- **Mode copies seules** (`c`) : ignore les mises à jour, ne copie que les fichiers absents en local
- **Bouton Stop** : interrompt le fichier en cours de transfert, passe au suivant
- **Progression détaillée** : barre de progression, volume cumulé / total, vitesse fichier et vitesse moyenne
- **Timestamps préservés** : après chaque copie le timestamp local est aligné sur celui du téléphone — les fichiers déjà copiés restent « identiques » au scan suivant
- **Robuste** : erreurs ADB gérées, transferts de très gros fichiers sans timeout
- **Push PC → Android** (`android-push`) : envoi incrémental d'un répertoire local vers le téléphone

---

## Prérequis

- Python ≥ 3.11
- [`adb`](https://developer.android.com/tools/adb) installé et dans le PATH (`android-tools-adb` sur Debian/Ubuntu)
- USB debugging activé sur le téléphone (*Paramètres → Options pour les développeurs → Débogage USB*)
- Téléphone déverrouillé et connecté en USB ; accepter la demande de débogage sur l'écran du téléphone

```bash
# Vérifier qu'adb voit le téléphone
adb devices
```

---

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/…/android-save.git
cd android-save

# Créer l'environnement et installer
uv venv
uv pip install -e ".[dev]"

# Lancer
uv run --no-project android-save
```

---

## Configuration

Au lancement, `android-save` cherche `backup_dir.toml` dans le répertoire courant,
puis dans `~/.config/android_save/` :

```toml
# backup_dir.toml
backup_dir = "~/android_backup"
```

Ce **répertoire de travail** contient les sauvegardes ainsi que les fichiers `.toml`
générés par l'écran de configuration :

| Fichier | Créé par | Contenu |
|---------|----------|---------|
| `save_android_{serial}_from_android.toml` | Scan du téléphone | Tous les dossiers de `/sdcard` |
| `save_android_{serial}_user.toml` | À la main (facultatif) | Liste personnalisée avec labels |
| `save_android_{serial}_todo.toml` | Bouton **Go** | Éléments cochés, passés à l'interface principale |

Si `backup_dir.toml` est absent, `~/android_backup` est utilisé par défaut.

Pour personnaliser la liste (labels, dossiers hors `/sdcard`) ou utiliser le mode
direct `--file`, le format `[[sync]]` est utilisé :

```toml
# [device]
# serial = "ABC123"   # décommentez si plusieurs appareils connectés

[[sync]]
remote = "/sdcard/DCIM"
local  = "~/android_backup/DCIM"
label  = "Photos / Vidéos"

[[sync]]
remote = "/sdcard/Documents"
local  = "~/android_backup/Documents"
label  = "Documents"

[[sync]]
remote = "/sdcard/WhatsApp"
local  = "~/android_backup/WhatsApp"
label  = "WhatsApp"
```

Chaque `[[sync]]` définit un couple à synchroniser. Le champ `label` est optionnel.

---

## Utilisation

```bash
# Flux standard : écran de configuration puis interface principale
android-save

# Inclure les mises à jour (défaut : copies seules)
android-save --no-copy-only

# Cibler un appareil précis
android-save --serial emulator-5554

# Bypass du setup avec un fichier TOML existant
android-save --file ~/android_backup/save_android_ABC123_todo.toml
```

---

## Push (PC → Android)

`android-push` envoie un répertoire local vers le téléphone : seuls les fichiers
absents (ou modifiés avec `--update`) sont transférés.

```bash
# Envoyer ~/Music vers /sdcard/Music (copies seules)
android-push ~/Music /sdcard/Music

# Simulation sans transfert réel
android-push ~/Music /sdcard/Music --dry-run

# Inclure les mises à jour
android-push ~/Music /sdcard/Music --update
```

---

## Interface TUI

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Android Save — Sauvegarde ADB          Appareil : OnePlus 5T (ABC123)   │
├──────────────────────────────┬──────────────────────────────────────────┤
│ Téléphone                    │ Backup → ~/android_backup/DCIM           │
│ /sdcard/DCIM                 │ ~/android_backup/DCIM                    │
│ ├── Camera/                  │ ├── Camera/                              │
│ │ ├── + IMG_0001.jpg  4.2 Mo │ │ ├── ~ IMG_0042.jpg  3.9 Mo            │
│ │ ├── ~ IMG_0042.jpg  3.9 Mo │ │ └──   IMG_0099.jpg  5.1 Mo            │
│ │ └──   IMG_0099.jpg  5.1 Mo │                                          │
├──────────────────────────────┴──────────────────────────────────────────┤
│ + à copier  ~ à mettre à jour    identique  ? orphelin (local seulement)│
├─────────────────────────────────────────────────────────────────────────┤
│ À traiter :                                                             │
│   ▶ Photos / Vidéos  (611 fichiers)                                     │
│   ○ Documents                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ [log]  Inventaire de /sdcard/DCIM…  611 fichiers sur le téléphone      │
│        611 à copier, 0 à mettre à jour, 0 identiques — 29.6 Go         │
├─────────────────────────────────────────────────────────────────────────┤
│ [████████████████░░░░] 8.3 Go / 29.6 Go  fichier: 12 Mo/s  moy.: 9 Mo/s│
│ /sdcard/DCIM/Camera/VID_20240715.mp4                                    │
│ Fichier 312 / 611  —  8.3 Go transférés                      [  Stop  ] │
└─────────────────────────────────────────────────────────────────────────┘
  s Synchroniser  c Copies seules  r Actualiser  q Quitter
```

### Code couleur des fichiers

| Couleur | Icône | Signification |
|---------|-------|---------------|
| **Vert** | `+` | Absent en local → sera copié |
| **Jaune** | `~` | Modifié → sera mis à jour |
| *Gris* | ` ` | Identique → ignoré |
| *Rouge italique* | `?` | Orphelin (présent en local seulement) |

### Raccourcis clavier

| Touche | Action |
|--------|--------|
| `s` | Lancer la synchronisation de tous les couples |
| `c` | Basculer le mode « copies seules » (sans mises à jour) |
| `r` | Actualiser l'inventaire du couple courant |
| `q` | Quitter |

### Bouton Stop

Pendant un transfert, le bouton **Stop** apparaît dans la barre de progression. Il interrompt le fichier en cours de copie et passe immédiatement au fichier suivant (le fichier partiel est supprimé).

---

## Flux de travail typique

1. Connecter le téléphone en USB
2. Accepter la demande de débogage USB sur l'écran du téléphone
3. Lancer `android-save` : dans l'écran de configuration, décocher les dossiers à exclure puis cliquer sur **Go**
4. Patienter pendant l'inventaire automatique du premier couple
5. Vérifier les panneaux (vert = à copier, jaune = à mettre à jour)
6. Appuyer sur `s`, confirmer dans la boîte de dialogue
7. Attendre la fin du transfert — les couples passent un par un de « À traiter » à « Traités »

---

## Structure du projet

```
android-save/
├── src/android_save/
│   ├── adb.py          # Wrapper ADB (détection, inventaire, transferts pull/push)
│   ├── sync.py         # Pull : comparaison et plan de synchronisation
│   ├── push.py         # Push : comparaison et plan d'envoi
│   ├── config.py       # Lecture/écriture des fichiers TOML
│   ├── tui/
│   │   ├── setup.py    # Écran de configuration (scan du téléphone, sélection)
│   │   ├── app.py      # Application Textual principale
│   │   ├── panels.py   # Panneaux d'arborescence colorés
│   │   ├── pairs.py    # Widget de suivi des couples
│   │   └── progress.py # Barre de progression avec vitesses
│   ├── __main__.py     # Point d'entrée `android-save`
│   └── _push_main.py   # Point d'entrée `android-push`
├── tests/              # 112 tests unitaires (pytest)
├── docs/               # Documentation Sphinx
├── backup_dir.toml     # Répertoire de travail (backups + fichiers générés)
└── open_doc.sh         # Ouvre la documentation HTML locale
```

---

## Tests

```bash
uv run --no-project pytest tests/ -v
```

---

## Documentation

```bash
# Construire la documentation Sphinx
.venv/bin/sphinx-build -b html docs/source docs/build/html

# Ouvrir dans le navigateur
./open_doc.sh
```

---

## Limitations connues

- Chaque commande est **unidirectionnelle** : `android-save` (téléphone → PC), `android-push` (PC → téléphone)
- Les fichiers orphelins (présents en local, absents du téléphone) sont signalés mais **jamais supprimés**
- `adb pull` ne supporte pas la reprise sur interruption : un fichier interrompu est supprimé et devra être recopié intégralement
- Requiert USB debugging — ne fonctionne pas en MTP

---

## Licence

MIT
