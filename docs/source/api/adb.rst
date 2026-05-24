Module ``android_save.adb``
===========================

.. automodule:: android_save.adb
   :members:
   :undoc-members:
   :show-inheritance:

Classes principales
-------------------

.. autoclass:: android_save.adb.AdbClient
   :members:
   :special-members: __init__

.. autoclass:: android_save.adb.Device
   :members:

.. autoclass:: android_save.adb.RemoteFile
   :members:

.. autoclass:: android_save.adb.PullProgress
   :members:

Exceptions
----------

.. autoclass:: android_save.adb.AdbError
   :members:

.. autoclass:: android_save.adb.DeviceNotFoundError
   :members:

.. seealso::

   :mod:`android_save.sync`
      Utilise :class:`~android_save.adb.RemoteFile` pour le calcul du plan.

   :mod:`android_save.tui.app`
      Appelle :meth:`~android_save.adb.AdbClient.pull_batch` pour les transferts.
