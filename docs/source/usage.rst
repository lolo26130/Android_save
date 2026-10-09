Utilisation
===========

Lancement
---------

Connectez votre téléphone en USB, puis depuis le répertoire du projet ::

    android-save

L'application démarre sur l'**interface de configuration** (:class:`~android_save.tui.setup.SetupApp`),
se connecte à l'appareil et propose deux modes de sélection avant d'ouvrir
l'interface principale.

Répertoire de travail (``backup_dir.toml``)
--------------------------------------------

Au lancement, ``android-save`` cherche ``backup_dir.toml`` dans le répertoire
courant, puis dans ``~/.config/android_save/``.

Ce fichier définit le répertoire où sont stockés **tous les fichiers ``.toml`` et
toutes les sauvegardes** :

.. code-block:: toml

    # backup_dir.toml
    backup_dir = "~/android_backup"

Si le fichier est absent, ``~/android_backup`` est utilisé par défaut.

Interface de configuration
---------------------------

Avant l'interface principale, un écran de configuration s'affiche :

.. code-block:: text

    Source de la liste :
      (●) Créer la liste depuis le téléphone
      (○) Utiliser le fichier utilisateur

    Éléments à synchroniser :
      [x] DCIM        (/sdcard/DCIM  ->  ~/android_backup/DCIM)
      [x] WhatsApp    (/sdcard/WhatsApp  ->  ~/android_backup/WhatsApp)
      [x] Documents   (/sdcard/Documents  ->  ~/android_backup/Documents)
      [ ] Music       (/sdcard/Music  ->  ~/android_backup/Music)
                                                          [ Go ]

Deux modes exclusifs (boutons radio) :

**Créer la liste depuis le téléphone**
    Scanne ``/sdcard`` et génère ``save_android_{serial}_from_android.toml``
    (écrase l'existant). Si ``save_android_{serial}_user.toml`` est présent,
    son existence est signalée dans la barre de statut.

**Utiliser le fichier utilisateur**
    Charge ``save_android_{serial}_user.toml`` — fichier créé manuellement
    pour personnaliser labels et chemins. Affiche un avertissement si absent.

La liste cochable se rafraîchit à chaque changement de mode. Décochez les
éléments à exclure de la sauvegarde, puis cliquez sur **Go**.

Le bouton **Go** génère ``save_android_{serial}_todo.toml`` (contenant uniquement
les éléments cochés) et lance l'interface principale avec ce fichier.

Fichiers générés dans le répertoire de backup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Fichier
     - Créé par
     - Contenu
   * - ``save_android_{serial}_from_android.toml``
     - Bouton « depuis le téléphone »
     - Tous les dossiers de ``/sdcard``
   * - ``save_android_{serial}_user.toml``
     - L'utilisateur (à la main)
     - Couples personnalisés avec labels
   * - ``save_android_{serial}_todo.toml``
     - Bouton **Go**
     - Éléments cochés — passé à l'interface principale

Options de la ligne de commande
--------------------------------

.. code-block:: text

    android-save [--file TOML] [--serial ID] [--no-copy-only]

    --file TOML       Fichier TOML existant (bypass l'interface de configuration)
    --serial ID       Forcer un appareil spécifique (utile si plusieurs téléphones)
    --no-copy-only    Désactiver le mode copies seules (activé par défaut)

Exemples ::

    # Flux standard (recommandé) — setup interactif puis interface principale
    android-save

    # Bypass du setup avec un fichier TOML existant
    android-save --file ~/android_backup/save_android_ABC123_todo.toml

    # Forcer un appareil et activer les mises à jour
    android-save --serial ABC123 --no-copy-only

Interface principale (TUI)
---------------------------

.. list-table::
   :header-rows: 1

   * - Touche
     - Action
   * - ``s``
     - Lancer la synchronisation de tous les couples
   * - ``c``
     - Basculer le mode « copies seules » (désactive/active les mises à jour)
   * - ``r``
     - Actualiser l'inventaire du couple courant
   * - ``q``
     - Quitter

Mode « copies seules » (défaut)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Au démarrage, l'interface est en **mode copies seules** : seuls les fichiers
**absents en local** sont copiés. Les fichiers déjà présents mais modifiés
(statut ``~``) sont ignorés.

Une bannière jaune le rappelle sous la légende :

.. code-block:: text

    ⚑ Mode : copies seules — les fichiers existants ne seront pas mis à jour

Appuyez sur ``c`` pour basculer vers le mode complet (copies + mises à jour),
ou utilisez ``--no-copy-only`` au lancement.

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

1. Connecter le téléphone en USB et accepter la demande de débogage.
2. Lancer ``android-save`` depuis le répertoire du projet.
3. Dans l'interface de configuration : choisir le mode, décocher les dossiers
   à exclure, cliquer **Go**.
4. Patienter pendant l'inventaire automatique du premier couple.
5. Vérifier le plan dans les panneaux (vert = à copier, jaune = à mettre à jour).
6. Appuyer sur ``s``, confirmer — tous les couples sont traités séquentiellement.
7. Attendre la fin du transfert (la section « Traités » se remplit au fur et à mesure).

Push PC → Android (``android-push``)
------------------------------------

La commande ``android-push`` effectue l'opération inverse : envoyer un répertoire
local vers l'appareil. Seuls les fichiers absents sont transférés par défaut
(``--update`` inclut les fichiers modifiés). Le répertoire distant est créé si
nécessaire.

.. code-block:: text

    android-push <source> <destination> [--serial ID] [--dry-run] [--update]

    source          Répertoire local à envoyer
    destination     Chemin distant sur l'appareil (ex: /sdcard/Music)
    --serial ID     Forcer un appareil spécifique
    --dry-run       Simulation sans copie réelle
    --update        Inclure les mises à jour (défaut : copies seules)

Exemples ::

    # Envoyer ~/Music vers /sdcard/Music (fichiers absents seulement)
    android-push ~/Music /sdcard/Music

    # Voir ce qui serait envoyé sans rien transférer
    android-push ~/Music /sdcard/Music --dry-run

    # Inclure les mises à jour (fichiers modifiés)
    android-push ~/Music /sdcard/Music --update
