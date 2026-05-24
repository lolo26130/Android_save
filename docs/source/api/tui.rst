Sous-package ``android_save.tui``
==================================

.. automodule:: android_save.tui
   :members:

Application principale
-----------------------

.. automodule:: android_save.tui.app
   :members:
   :show-inheritance:

.. autoclass:: android_save.tui.app.AndroidSaveApp
   :members:
   :special-members: __init__

.. autoclass:: android_save.tui.app.ConfirmScreen
   :members:

Panneaux d'arborescence
------------------------

.. automodule:: android_save.tui.panels
   :members:
   :show-inheritance:

.. autoclass:: android_save.tui.panels.FileTreePanel
   :members:

Widget des couples de dossiers
-------------------------------

.. automodule:: android_save.tui.pairs
   :members:
   :show-inheritance:

.. autoclass:: android_save.tui.pairs.FolderPairsPanel
   :members:
   :special-members: __init__

.. autoclass:: android_save.tui.pairs.PairStatus
   :members:

.. autoclass:: android_save.tui.pairs.PairState
   :members:

Barre de progression
---------------------

.. automodule:: android_save.tui.progress
   :members:
   :show-inheritance:

.. autoclass:: android_save.tui.progress.TransferProgress
   :members:

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
