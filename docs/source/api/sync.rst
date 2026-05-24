Module ``android_save.sync``
============================

.. automodule:: android_save.sync
   :members:
   :undoc-members:
   :show-inheritance:

Moteur de synchronisation
--------------------------

.. autoclass:: android_save.sync.SyncEngine
   :members:
   :special-members: __init__

Plan de synchronisation
-----------------------

.. autoclass:: android_save.sync.SyncPlan
   :members:

.. autoclass:: android_save.sync.SyncEntry
   :members:

.. autoclass:: android_save.sync.FileStatus
   :members:

Inventaire local
----------------

.. autoclass:: android_save.sync.LocalInventory
   :members:

Utilitaires
-----------

.. autofunction:: android_save.sync.format_size

.. seealso::

   :mod:`android_save.adb`
      Fournit les :class:`~android_save.adb.RemoteFile` passés à
      :meth:`~android_save.sync.SyncEngine.compute`.

   :mod:`android_save.tui.panels`
      Consomme le :class:`~android_save.sync.SyncPlan` pour l'affichage.
