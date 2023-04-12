import asyncio
import logging
from abc import abstractmethod
from typing import Dict, Optional, Set, Tuple, Type, Union

from tickit.core.management.event_router import InverseWiring, Wiring
from tickit.core.management.ticker import Ticker
from tickit.core.state_interfaces import StateConsumer, StateProducer
from tickit.core.typedefs import (
    ComponentException,
    ComponentID,
    Input,
    Interrupt,
    Output,
    SimTime,
    StopComponent,
)
from tickit.utils.topic_naming import input_topic, output_topic

LOGGER = logging.getLogger(__name__)


class BaseScheduler:
    """A base scheduler class which implements logic common to all schedulers."""

    def __init__(
        self,
        wiring: Union[Wiring, InverseWiring],
        state_consumer: Type[StateConsumer],
        state_producer: Type[StateProducer],
    ) -> None:
        """A constructor which stores inputs and creates an empty wakeups mapping.

        Args:
            wiring (Union[Wiring, InverseWiring]): A wiring or inverse wiring object
                representing the connections between components in the system.
            state_consumer (Type[StateConsumer]): The state consumer class to be used
                by the component.
            state_producer (Type[StateProducer]): The state producer class to be used
                by the component.
        """
        self._wiring = wiring
        self._state_consumer_cls = state_consumer
        self._state_producer_cls = state_producer
        self.wakeups: Dict[ComponentID, SimTime] = dict()

        self.error = asyncio.Event()

    @abstractmethod
    async def schedule_interrupt(self, source: ComponentID) -> None:
        """An abstract asynchronous method which should schedule an interrupt
        immediately.

        Args:
            source (ComponentID): The component which should be updated.
        """
        raise NotImplementedError

    async def update_component(self, input: Input) -> None:
        """Sends a message with an input to the input topic of a component.

        Args:
            input (Input): The input to be included in the message sent to the
                component.
        """
        await self.state_producer.produce(input_topic(input.target), input)

    async def handle_message(
        self, message: Union[Interrupt, Output, ComponentException]
    ) -> None:
        """Handle messages recieved by the state consumer.

        An asynchronous callback which handles Interrupt, Output and ComponentException
        messages recieved by the state consumer. For Outputs, changes are propagated
        and wakeups scheduled if required. For interrupts handling is deferred. For
        exceptions, a StopComponent message is produced to each component in the system
        to facilitate shut down.

        Args:
            message (Union[Interrupt, Output, ComponentException]): An Interrupt,
                Output or ComponentException recieved by the state consumer.
        """
        LOGGER.debug("Scheduler ({}) got {}".format(type(self).__name__, message))
        if isinstance(message, Output):
            await self.ticker.propagate(message)
            if message.call_at is not None:
                self.add_wakeup(message.source, message.call_at)
        elif isinstance(message, Interrupt):
            await self.schedule_interrupt(message.source)
        elif isinstance(message, ComponentException):
            await self.handle_component_exception(message)

    async def setup(self) -> None:
        """Instantiates and configures the ticker and state interfaces.

        An asynchronous setup method which creates a ticker, a state consumer which is
        subscribed to the output topics of each component in the system, a state
        producer to produce component inputs.
        """
        self.ticker = Ticker(self._wiring, self.update_component)
        self.state_consumer: StateConsumer[
            Union[Interrupt, Output, ComponentException]
        ] = self._state_consumer_cls(self.handle_message)
        await self.state_consumer.subscribe(
            {output_topic(component) for component in self.ticker.components}
        )
        self.state_producer: StateProducer[
            Union[Input, StopComponent, ComponentException]
        ] = self._state_producer_cls()

    def add_wakeup(self, component: ComponentID, when: SimTime) -> None:
        """Adds a wakeup to the mapping.

        Args:
            component (ComponentID): The component which should be updated.
            when (SimTime): The simulation time at which the update should occur.
        """
        LOGGER.debug("Scheduling {} for wakeup at {}".format(component, when))
        self.wakeups[component] = when

    def get_first_wakeups(self) -> Tuple[Set[ComponentID], Optional[SimTime]]:
        """Gets the components which are due for update first and the wakeup time.

        A method which returns a set of components which are due for update first and
        the simulation time at which the updates are scheduled. Or an empty set and
        None if no wakeups are scheduled.

        Returns:
            Tuple[Set[ComponentID], Optional[SimTime]]: A tuple containing the set of
                components which are scheduled for the first wakeup and the time at
                which the wakeup should occur. Or an empty set and None if no wakeups
                are scheduled.
        """
        if not self.wakeups:
            return set(), None
        first = min(self.wakeups.values())
        components = {
            component for component, when in self.wakeups.items() if when == first
        }
        return components, first

    async def handle_component_exception(self, message: ComponentException) -> None:
        """Handle exceptions raised from componenets by shutting down the simulation.

        If a component produces an exception, the scheduler will produce a message to
        all components in the simulation to cause them to cancel any running component
        tasks. After which the scheduler shuts its self down.

        """
        await asyncio.wait(
            {
                asyncio.create_task(
                    self.state_producer.produce(input_topic(component), StopComponent())
                )
                for component in self.ticker.components
            },
            return_when=asyncio.tasks.ALL_COMPLETED,
        )
        self.error.set()
