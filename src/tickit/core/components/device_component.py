import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Hashable, List, Mapping, Type, cast

from immutables import Map

from tickit.core.adapter import AdapterContainer
from tickit.core.components.component import BaseComponent
from tickit.core.device import Device, DeviceUpdate
from tickit.core.state_interfaces import StateConsumer, StateProducer
from tickit.core.typedefs import Changes, ComponentID, SimTime, State

InterruptHandler = Callable[[], Awaitable[None]]


LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceComponent(BaseComponent):
    """A component containing a device and the corresponding adapters.

    A component which thinly wraps a device and the corresponding adapters, this
    component delegates core behaviour to the update method of the device, whilst
    allowing adapters to raise interrupts.
    """

    name: ComponentID
    device: Device
    adapters: List[AdapterContainer] = field(default_factory=list)
    last_outputs: State = field(init=False, default_factory=lambda: State({}))
    device_inputs: Dict[str, Hashable] = field(init=False, default_factory=dict)
    _tasks: List[asyncio.Task] = field(default_factory=list)

    async def run_forever(
        self, state_consumer: Type[StateConsumer], state_producer: Type[StateProducer]
    ) -> None:
        """Set up state interfaces, run adapters and blocks until any complete."""
        self._tasks = [
            asyncio.create_task(adapter.run_forever(self.raise_interrupt))
            for adapter in self.adapters
        ]

        await super().run_forever(state_consumer, state_producer)
        if self._tasks:
            await asyncio.wait(self._tasks)

    async def on_tick(self, time: SimTime, changes: Changes) -> None:
        """Delegates core behaviour to the device and calls adapter on_update.

        An asynchronous method which updates device inputs according to external
        changes, delegates core behaviour to the device update method, informs
        Adapters of the update, computes changes to the state of the component
        and sends the resulting Output.

        Args:
            time (SimTime): The current simulation time (in nanoseconds).
            changes (Changes): A mapping of changed component inputs and their new
                values.
        """
        self.device_inputs = {
            **self.device_inputs,
            **cast(Mapping[str, Hashable], changes),
        }
        device_update: DeviceUpdate = self.device.update(
            SimTime(time), self.device_inputs
        )
        for adapter in self.adapters:
            adapter.adapter.after_update()
        out_changes = Changes(
            Map(
                {
                    k: v
                    for k, v in device_update.outputs.items()
                    if k not in self.last_outputs or not self.last_outputs[k] == v
                }
            )
        )
        self.last_outputs = device_update.outputs
        await self.output(time, out_changes, device_update.call_at)

    async def stop_component(self) -> None:
        """Cancel all pending tasks associated with the device component.

        Cancels long running adapter tasks associated with the component.
        """
        LOGGER.debug(f"Stopping {self.name}")
        for task in self._tasks:
            task.cancel()
