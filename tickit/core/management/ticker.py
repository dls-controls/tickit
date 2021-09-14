import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional, Set, Union

from immutables import Map

from tickit.core.management.event_router import EventRouter, InverseWiring, Wiring
from tickit.core.typedefs import Changes, ComponentID, Input, Output, SimTime

LOGGER = logging.getLogger(__name__)


class Ticker:
    """A utility class responsible for sequencing the update of components during a tick

    A utility class responsible for sequencing the update of components during a tick
    by eagerly updating each component which has had all of its dependencies resolved
    """

    def __init__(
        self,
        wiring: Union[Wiring, InverseWiring],
        update_component: Callable[[Input], Awaitable[None]],
    ) -> None:
        """A constructor which creates an event router and performs initial setup

        Args:
            wiring (Union[Wiring, InverseWiring]): A wiring or inverse wiring object
                representing the connections between components in the system
            update_component (Callable[[Input], Awaitable[None]]): A function or method
                which may be called to request a component performs and update, such
                updates should result in a subsequent call to the propagate method of
                the ticker
        """
        self.event_router = EventRouter(wiring)
        self.update_component = update_component
        self.to_update: Dict[ComponentID, Optional[asyncio.Task]] = dict()
        self.finished: asyncio.Event = asyncio.Event()

    async def __call__(
        self, time: SimTime, update_components: Set[ComponentID]
    ) -> None:
        """An asynchronous method which performs a tick

        An asynchronous method which performs a tick by setting up the initial state of
        the system during the tick - including determining dependant components,
        scheduling updates which require no component resolutions to be performed,
        before blocking until the system is resolved by update propagation

        Args:
            time (SimTime): The simulation time at which the tick occurs (in
                nanoseconds)
            update_components (Set[ComponentID]): A set of components which require
                update
        """
        await self._start_tick(time, update_components)
        await self.schedule_possible_updates()
        await self.finished.wait()
        self.finished.clear()

    async def _start_tick(self, time: SimTime, update_components: Set[ComponentID]):
        """An asynchronous method which sets up the ticker to perform a tick

        An asynchronous method which sets up the ticker to perform a tick by updating
        time, reseting accumulators and finding the set of components which require
        update

        Args:
            time (SimTime): The simulation time at which the tick occurs (in
                nanoseconds)
            update_components (Set[ComponentID]): A set of components which require
                update
        """
        self.time = time
        LOGGER.debug("Doing tick @ {}".format(self.time))
        self.inputs: Set[Input] = set()
        self.to_update = {
            c: None
            for component in update_components
            for c in self.event_router.dependants(component)
        }

    async def schedule_possible_updates(self) -> None:
        """An asynchronous method which updates components with resolved dependencies

        An asynchronous method which schedules updates for components with resolved
        dependencies, as determined by the intersection of the components first order
        dependencies and the set of componets which still require an update
        """
        self.to_update.update(
            {
                component: asyncio.create_task(
                    self.update_component(
                        self.collate_inputs(self.inputs, component, self.time)
                    )
                )
                for component, task in self.to_update.items()
                if task is None
                and not self.event_router.inverse_component_tree[
                    component
                ].intersection(self.to_update)
            }
        )

    def collate_inputs(
        self, inputs: Set[Input], component: ComponentID, time: SimTime
    ) -> Input:
        """A utility method for collating the changes across multiple component inputs

        Args:
            inputs (Set[Input]): A set of all inputs
            component (ComponentID): The component for which the inputs should be
                collated
            time (SimTime): The time at which the inputs should be collated

        Returns:
            Input:
                An input to the component at the time specified with changes collated
                from each relevent input in the inputs set
        """
        return Input(
            component,
            time,
            Changes(
                Map(
                    {
                        k: v
                        for input in inputs
                        if input.target == component and input.time == time
                        for k, v in input.changes.items()
                    }
                )
            ),
        )

    async def propagate(self, output: Output) -> None:
        """An asynchronous message which propagates the output of an updated component

        An asynchronous message which propagates the output of an updated component by
        removing the component from the set of components requiring update, adding the
        routed inputs to the accumulator, and scheduling any possible updates. If no
        components require update the finsihed flag will be set

        Args:
            output (Output): The output produced by the update of a component
        """
        assert output.source in self.to_update.keys()
        assert output.time == self.time
        self.to_update.pop(output.source)
        self.inputs.update(self.event_router.route(output))
        await self.schedule_possible_updates()
        if not self.to_update:
            self.finished.set()

    @property
    def components(self) -> Set[ComponentID]:
        """A property which returns a set of all components in the wiring

        Returns:
            Set[ComponentID]: A set of all components in the wiring
        """
        return self.event_router.components
