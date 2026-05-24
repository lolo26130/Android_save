Utilisation
===========

Lancement rapide
----------------

Connectez votre téléphone en USB, puis::

    android-save

L'application détecte automatiquement l'appareil et lance l'inventaire de ``/sdcard``.

Options de la ligne de commande
--------------------------------

.. code-block:: text

    android-save [--remote CHEMIN] [--local CHEMIN] [--serial ID]

    --remote CHEMIN   Répertoire source sur le téléphone (défaut: /sdcard)
    --local CHEMIN    Répertoire de backup local (défaut: ~/android_backup)
    --serial ID       Forcer un appareil spécifique (utile si plusieurs téléphones)

Exemples::

    # Sauvegarder uniquement les photos
    android-save --remote /sdcard/DCIM --local ~/Photos_Android

    # Cibler un appareil précis
    android-save --serial emulator-5554

Interface TUI
-------------

.. list-table::
   :header-rows: 1

   * - Touche
     - Action
   * - ``s``
     - Lancer la synchronisation
   * - ``r``
     - Actualiser l'inventaire
   * - ``q``
     - Quitter

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
3. Lancer ``android-save``.
4. Attendre la fin de l'inventaire (quelques secondes).
5. Vérifier le plan de synchronisation dans les deux panneaux.
6. Appuyer sur ``s`` et confirmer.
7. Attendre la fin du transfert.
