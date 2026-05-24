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

Barre de progression
---------------------

.. automodule:: android_save.tui.progress
   :members:
   :show-inheritance:

.. autoclass:: android_save.tui.progress.TransferProgress
   :members:

.. seealso::

   :mod:`android_save.adb`
      Fournit :class:`~android_save.adb.AdbClient` et
      :class:`~android_save.adb.PullProgress` utilisés dans
      :meth:`~android_save.tui.app.AndroidSaveApp.start_transfer`.

   :mod:`android_save.sync`
      Fournit :class:`~android_save.sync.SyncPlan` affiché dans
      :class:`~android_save.tui.panels.FileTreePanel`.
