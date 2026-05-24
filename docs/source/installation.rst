Installation
============

Prérequis système
-----------------

- Python 3.11+
- ``adb`` installé (paquet ``adb`` ou ``android-tools-adb``) ::

    sudo apt install adb

- USB debugging activé sur le téléphone Android :

  1. Paramètres → À propos du téléphone → Numéro de build (appuyer 7 fois)
  2. Paramètres → Options pour les développeurs → Débogage USB : **Activé**

Installation du package
-----------------------

Via ``uv`` (recommandé)::

    uv sync

En mode développement::

    uv sync --extra dev --extra docs

Vérification
------------

::

    android-save --help
