Module ``android_save.config``
==============================

.. automodule:: android_save.config
   :members:
   :undoc-members:
   :show-inheritance:

Classes principales
-------------------

.. autoclass:: android_save.config.FolderPair
   :members:

.. autoclass:: android_save.config.Config
   :members:

Chargement et écriture
-----------------------

.. autofunction:: android_save.config.load_config

.. autofunction:: android_save.config.write_config

.. autofunction:: android_save.config.read_backup_dir

.. autofunction:: android_save.config.default_config_path

Exceptions
----------

.. autoclass:: android_save.config.ConfigError
   :members:

Exemple de fichier TOML
-----------------------

.. code-block:: toml

    [device]
    serial = "ABC123"   # optionnel — utile si plusieurs appareils connectés

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

.. seealso::

   :mod:`android_save.tui.pairs`
      Utilise :class:`~android_save.config.FolderPair` pour afficher l'état
      de chaque couple dans l'interface.

   :mod:`android_save.tui.app`
      :class:`~android_save.tui.app.AndroidSaveApp` reçoit la liste de
      :class:`~android_save.config.FolderPair` et orchestre les transferts.
