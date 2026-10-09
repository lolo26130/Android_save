Module ``android_save.push``
============================

.. automodule:: android_save.push

Classes principales
-------------------

.. autoclass:: android_save.push.PushEngine
   :members:

.. autoclass:: android_save.push.PushPlan
   :members:

.. autoclass:: android_save.push.PushEntry
   :members:

.. autoclass:: android_save.push.PushStatus
   :members:

Commande ``android-push``
--------------------------

.. code-block:: text

    android-push <source> <destination> [--serial ID] [--dry-run] [--update]

    source          Répertoire local à envoyer
    destination     Chemin distant sur l'appareil (ex: /sdcard/Music)
    --serial ID     Forcer un appareil spécifique
    --dry-run       Simulation sans copie réelle
    --update        Mettre à jour les fichiers modifiés (par défaut : copies seules)

Exemples ::

    # Envoyer ~/Music vers /sdcard/Music (fichiers absents seulement)
    android-push ~/Music /sdcard/Music

    # Voir ce qui serait copié sans rien transférer
    android-push ~/Music /sdcard/Music --dry-run

    # Inclure les mises à jour (fichiers modifiés)
    android-push ~/Music /sdcard/Music --update

    # Forcer un appareil spécifique
    android-push ~/Music /sdcard/Music --serial 71991fe3

.. seealso::

   :mod:`android_save.adb`
      Fournit :meth:`~android_save.adb.AdbClient.push` et
      :meth:`~android_save.adb.AdbClient.push_batch` utilisés pour
      les transferts effectifs.

   :mod:`android_save.sync`
      Moteur de synchronisation en sens inverse (Android → PC),
      dont :class:`~android_save.sync.LocalInventory` est réutilisé ici.
