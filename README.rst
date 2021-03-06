=========
simpleisy
=========

Python library for Universal Devices ISY994 Insteon/ZWave controller hub

This library transforms the XML from the ISY into more pythonic data structures and provides both an object model interface as
well as a more procedural/lower interface for commands.

Usage
=====

The ``ISYController`` object provides methods to get devices and programs. GetDevice and GetProgram return ``ISYDevice`` and
``ISYProgram`` objects, respectively, and those objects provide methods to turn devices on/off, run programs, etc.

.. code:: python

    from simpleisy import ISYController
    isy = ISYController("1.2.3.4", "admin", "password")
    dev = isy.GetDevice("Living room lights")
    print dev.GetState()
    dev.TurnOn()

Output::

    Off

You can also use device/program commands more directly if you want by directly calling ``NodeCommand`` or ``ProgramCommand``

.. code:: python

    from simpleisy import ISYController
    isy = ISYController("1.2.3.4", "admin", "password")

    node_address = "1A 2B 3C"

    # Turn on the device
    isy.NodeCommand(node_address, "DON")

    # Turn off the device
    isy.NodeCommand(node_address, "DOF")
