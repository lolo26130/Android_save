Module ``android_save.adb``
===========================

.. automodule:: android_save.adb

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

.. autoclass:: android_save.adb.PushProgress
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

   :mod:`android_save.push`
      Utilise :meth:`~android_save.adb.AdbClient.push` et
      :meth:`~android_save.adb.AdbClient.push_batch` pour l'envoi PC → Android.
