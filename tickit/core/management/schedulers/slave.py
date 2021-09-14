import logging
from typing import Awaitable, Callable, Dict, Optional, Set, Tuple, Type, Union

from immutables import Map

from tickit.core.management.event_router import InverseWiring, Wiring
from tickit.core.management.schedulers.base import BaseScheduler
from tickit.core.state_interfaces.state_interface import StateConsumer, StateProducer
from tickit.core.typedefs import (
    Changes,
    ComponentID,
    ComponentPort,
    Input,
    Output,
    PortID,
    SimTime,
)

LOGGER = logging.getLogger(__name__)


class SlaveScheduler(BaseScheduler):
    """A slave scheduler which orchestrates nested tickit simulations"""

    def __init__(
        self,
        wiring: Union[Wiring, InverseWiring],
        state_consumer: Type[StateConsumer],
        state_producer: Type[StateProducer],
        expose: Dict[PortID, ComponentPort],
        raise_interrupt: Callable[[], Awaitable[None]],
    ) -> None:
        """A constructor of the slave scheduler which adds wiring and saves values for reference

        Args:
            wiring (Union[Wiring, InverseWiring]): A wiring or inverse wiring object
                representing the connections between components in the system
            state_consumer (Type[StateConsumer]): The state consumer class to be used
                by the component
            state_producer (Type[StateProducer]): The state producer class to be used
                by the component
            expose (Dict[PortID, ComponentPort]): A mapping of slave scheduler
                outputs to internal component ports
            raise_interrupt (Callable[[], Awaitable[None]]): A callback to request that
                the slave scheduler is updated immediately
        """
        wiring = self.add_exposing_wiring(wiring, expose)
        super().__init__(wiring, state_consumer, state_producer)

        self.raise_interrupt = raise_interrupt
        self.interrupts: Set[ComponentID] = set()

    @staticmethod
    def add_exposing_wiring(
        wiring: Union[Wiring, InverseWiring],
        expose: Dict[PortID, ComponentPort],
    ) -> InverseWiring:
        """A utility function which adds wiring to expose slave scheduler outputs

        A utility function which adds wiring to expose slave scheduler outputs, this is
        performed creating a mock "expose" component with inverse wiring set by expose

        Args:
            wiring (Union[Wiring, InverseWiring]): A wiring or inverse wiring object
                representing the connections between components in the system
            expose (Dict[PortID, ComponentPort]): A mapping of slave scheduler
                outputs to internal component ports

        Returns:
            InverseWiring:
                An inverse wiring object representing the connections between
                components in the system and the "expose" component which acts as the
                slave scheduler output
        """
        if isinstance(wiring, Wiring):
            wiring = InverseWiring.from_wiring(wiring)
        wiring[ComponentID("expose")].update(expose)
        return wiring

    async def update_component(self, input: Input) -> None:
        """An asynchronous method which mocks I/O or sends an input to a component

        An asynchronous method mocks the "external" and "expose" components of the
        simulation, sending extenral inputs and storing outputs respectively; For real
        components the input message is sent to their input topic

        Args:
            input (Input): The input message to be sent to the component
        """
        if input.target == ComponentID("external"):
            await self.ticker.propagate(
                Output(ComponentID("external"), input.time, self.input_changes, None)
            )
        elif input.target == ComponentID("expose"):
            self.output_changes = input.changes
            await self.ticker.propagate(
                Output(ComponentID("expose"), input.time, Changes(Map()), None)
            )
        else:
            await super().update_component(input)

    async def on_tick(
        self, time: SimTime, changes: Changes
    ) -> Tuple[Changes, Optional[SimTime]]:
        """An asynchronous method which routes inputs, performs a tick and sends outputs

        An asyhcnronous method which determines which components within the simulation
        require being woken up, sets the input changes for use by the "external" mock
        component, performs a tick, determines the period in which the slave scheduler
        should next be updated, and returns the changes collated by the "expose" mock
        component

        Args:
            time (SimTime): The current simulation time (in nanoseconds)
            changes (Changes): A mapping of changed component inputs and their new
                values

        Returns:
            Tuple[Changes, Optional[SimTime]]:
                A tuple of a mapping of the changed exposed outputs and their new
                values and optionally a duration in simulation time after which the
                slave scheduler should be called again
        """

        root_components: Set[ComponentID] = {
            *self.interrupts,
            *(wakeup.component for wakeup in await self.wakeups.all_lt(time)),
            ComponentID("external"),
        }
        self.interrupts.clear()

        self.input_changes = changes
        self.output_changes = Changes(Map())
        await self.ticker(time, root_components)

        call_in = None
        if not self.wakeups.empty():
            priority, wakeup = await self.wakeups.get()
            call_in = SimTime(wakeup.when - time)
            self.wakeups.put((priority, wakeup))

        return self.output_changes, call_in

    async def run_forever(self) -> None:
        """An asynchronous method which delegates to setup to run continiously"""
        await self.setup()

    async def schedule_interrupt(self, source: ComponentID) -> None:
        """An asynchronous method which schedules an interrupt immediately

        An asynchronous method which schedules an interrupt immediately by adding it to
        a set of queued interrupts and raising the interrupt to the master scheduler

        Args:
            component (ComponentID): The component which should be updated
        """
        LOGGER.debug("Adding {} to interrupts".format(source))
        self.interrupts.add(source)
        await self.raise_interrupt()
