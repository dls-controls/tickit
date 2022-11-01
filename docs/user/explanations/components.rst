Simulation Components
=====================

There are two types of components that can be used in a tickit simulation,
device simulations and system simulations.

Device Simulation
-----------------

Device simulations are the typical use case of a component. They encapsulate a
device and any adapters for that device.

.. figure:: ../images/tickit-device-simulation-cpt.svg
    :align: center


System Simulation
-----------------

System simulation components are themselves entire tickit simulations. They
contain their own device simulation components and a scheduler for orchestrating
them. However, the scheduler in a system component acts as a slave scheduler
which is driven by the master scheduler in the top level of the simulation
it belongs to.

.. figure:: ../images/tickit-system-simulation-cpt.svg
    :align: center

System simulations can also contain their own system simulation components
allowing for the construction of reasonably complex systems.

To configure a system simulation the config.yaml the system simulation components
and their respective components are nested in the config.yaml in order to
populate the wiring for the master scheduler. For example:

.. code-block:: yaml

    - examples.devices.trampoline.RandomTrampoline:
    name: random_trampoline
    inputs: {}
    callback_period: 10000000000
    - tickit.core.components.system_simulation.SystemSimulation:
        name: internal_tickit
        inputs:
        input_1: random_trampoline:output
        components:
        - tickit.devices.sink.Sink:
            name: internal_sink
            inputs:
                sink_1: external:input_1
        - examples.devices.remote_controlled.RemoteControlled:
            name: internal_tcp_controlled
            inputs: {}
        expose:
        output_1: internal_tcp_controlled:observed
    - tickit.devices.sink.Sink:
        name: external_sink
        inputs:
        sink_1: internal_tickit:output_1



The Overall Simulation
-------------------------------

.. figure:: ../images/tickit-simple-overview-with-system-simulation.svg
    :align: center