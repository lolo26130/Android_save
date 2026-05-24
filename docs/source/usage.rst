Utilisation
===========

Lancement rapide
----------------

Connectez votre téléphone en USB, puis::

    android-save --file ~/android_save.toml

L'application détecte automatiquement l'appareil, lance l'inventaire du premier
couple et affiche la liste de tous les couples à synchroniser.

Options de la ligne de commande
--------------------------------

.. code-block:: text

    android-save [--file TOML] [--remote CHEMIN] [--local CHEMIN] [--serial ID] [--copy-only]

    --file TOML       Fichier TOML définissant les couples de dossiers (recommandé)
    --remote CHEMIN   Répertoire source sur le téléphone (défaut: /sdcard)
    --local CHEMIN    Répertoire de backup local (défaut: ~/android_backup)
    --serial ID       Forcer un appareil spécifique (utile si plusieurs téléphones)
    --copy-only       Copier uniquement les fichiers absents (ignorer les mises à jour)

.. note::
    ``--remote`` et ``--local`` sont ignorés si ``--file`` est fourni.
    Le serial défini dans le fichier TOML est prioritaire sur ``--serial``
    s'ils sont tous les deux absents.

Exemples::

    # Mode multi-dossiers via fichier de configuration (recommandé)
    android-save --file ~/android_save.toml

    # Mode simple dossier (rétrocompatible)
    android-save --remote /sdcard/DCIM --local ~/Photos_Android

    # Cibler un appareil précis avec un fichier de config
    android-save --file ~/android_save.toml --serial emulator-5554

    # Copies seules (ne pas écraser les fichiers déjà présents en local)
    android-save --file ~/android_save.toml --copy-only

Fichier de configuration TOML
------------------------------

Créez ``~/android_save.toml`` :

.. code-block:: toml

    [device]
    serial = "ABC123"   # optionnel

    [[sync]]
    remote = "/sdcard/DCIM"
    local  = "~/backup/Photos"
    label  = "Photos"

    [[sync]]
    remote = "/sdcard/WhatsApp"
    local  = "~/backup/WhatsApp"
    label  = "WhatsApp"

    [[sync]]
    remote = "/sdcard/Documents"
    local  = "~/backup/Documents"

Chaque entrée ``[[sync]]`` définit un couple à synchroniser. Le champ
``label`` est optionnel et sert à l'affichage dans l'interface.

.. seealso::
    :mod:`android_save.config` — documentation complète du format TOML.

Interface TUI
-------------

.. list-table::
   :header-rows: 1

   * - Touche
     - Action
   * - ``s``
     - Lancer la synchronisation de tous les couples
   * - ``c``
     - Basculer le mode « copies seules » (désactive les mises à jour)
   * - ``r``
     - Actualiser l'inventaire du couple courant
   * - ``q``
     - Quitter

Mode « copies seules »
~~~~~~~~~~~~~~~~~~~~~~~

La touche ``c`` (ou l'option ``--copy-only``) active un mode dans lequel seuls
les fichiers **absents en local** sont copiés. Les fichiers déjà présents mais
modifiés (statut ``~``) sont ignorés.

Une bannière jaune s'affiche sous la légende pour rappeler que ce mode est actif :

.. code-block:: text

    ⚑ Mode : copies seules — les fichiers existants ne seront pas mis à jour

Appuyez à nouveau sur ``c`` pour revenir au mode normal (copies + mises à jour).

Panneau des couples de dossiers
---------------------------------

Entre la légende et le log, deux sections colorées affichent l'état
de chaque couple :

.. list-table::
   :header-rows: 1

   * - Icône / couleur
     - Signification
   * - ``○`` blanc
     - En attente
   * - ``▶`` jaune
     - En cours (inventaire ou transfert)
   * - ``✓`` vert
     - Terminé avec succès
   * - ``✗`` rouge
     - Terminé avec erreurs

Code couleur des fichiers
--------------------------

.. list-table::
   :header-rows: 1

   * - Couleur
     - Signification
   * - **Vert** (``+``)
     - Absent en local → sera copié
   * - **Jaune** (``~``)
     - Modifié → sera mis à jour
   * - *Gris*
     - Identique → ignoré
   * - *Rouge italique* (``?``)
     - Orphelin (présent en local seulement)

Flux de travail typique
------------------------

1. Connecter le téléphone en USB.
2. Accepter la demande de débogage USB sur le téléphone.
3. Créer ou éditer ``~/android_save.toml`` avec les couples souhaités.
4. Lancer ``android-save --file ~/android_save.toml``.
5. Patienter pendant l'inventaire du premier couple.
6. Vérifier le plan dans les panneaux et la liste des couples.
7. Appuyer sur ``s``, confirmer — tous les couples sont traités séquentiellement.
8. Attendre la fin du transfert (la section « Traités » se remplit au fur et à mesure).
