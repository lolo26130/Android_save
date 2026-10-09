Sous-package ``android_save.tui``
==================================

.. automodule:: android_save.tui

Interface de configuration
---------------------------

.. automodule:: android_save.tui.setup

.. autoclass:: android_save.tui.setup.SetupApp
   :members:
   :special-members: __init__
   :exclude-members: BINDINGS, DEFAULT_CSS, TITLE

Application principale
-----------------------

.. automodule:: android_save.tui.app

.. autoclass:: android_save.tui.app.AndroidSaveApp
   :members:
   :special-members: __init__
   :exclude-members: BINDINGS, DEFAULT_CSS, TITLE

.. autoclass:: android_save.tui.app.ConfirmScreen
   :members:
   :exclude-members: DEFAULT_CSS

Panneaux d'arborescence
------------------------

.. automodule:: android_save.tui.panels

.. autoclass:: android_save.tui.panels.FileTreePanel
   :members:
   :exclude-members: DEFAULT_CSS

Widget des couples de dossiers
-------------------------------

.. automodule:: android_save.tui.pairs

.. autoclass:: android_save.tui.pairs.FolderPairsPanel
   :members:
   :special-members: __init__
   :exclude-members: DEFAULT_CSS

.. autoclass:: android_save.tui.pairs.PairStatus
   :members:

.. autoclass:: android_save.tui.pairs.PairState
   :members:

Barre de progression
---------------------

.. automodule:: android_save.tui.progress

.. autoclass:: android_save.tui.progress.TransferProgress
   :members:
   :exclude-members: DEFAULT_CSS

.. seealso::

   :mod:`android_save.config`
      Fournit :class:`~android_save.config.FolderPair` consommé par
      :class:`~android_save.tui.pairs.FolderPairsPanel` et
      :class:`~android_save.tui.app.AndroidSaveApp`.

   :mod:`android_save.adb`
      Fournit :class:`~android_save.adb.AdbClient` et
      :class:`~android_save.adb.PullProgress` utilisés dans
      :meth:`~android_save.tui.app.AndroidSaveApp.sync_all_pairs`.

   :mod:`android_save.sync`
      Fournit :class:`~android_save.sync.SyncPlan` affiché dans
      :class:`~android_save.tui.panels.FileTreePanel`.
