from pathlib import Path

from softioc import builder

from tickit.adapters.epicsadapter import EpicsAdapter
from tickit.core.adapter import RaiseInterrupt
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.compat.typing_compat import TypedDict


class PneumaticDevice(Device):
    """Pneumatic Device with movement controls."""

    #: A typed mapping containing the current output value
    Outputs: TypedDict = TypedDict("Outputs", {"output": float})

    def __init__(
        self,
        initial_speed: float,
        initial_state: bool,
    ) -> None:
        """Initialise a Pneumatic object."""
        self.speed: float = initial_speed
        self.state: bool = initial_state
        self.moving: bool = False
        self.time_at_last_update: float = 0.0

    def set_speed(self, speed: float) -> None:
        """Set the speed of movement for the device.

        Args:
            speed (float): The desired movement speed of the device.
        """
        self.speed = speed

    def get_speed(self) -> float:
        """Get the speed of movement of the device."""
        return self.speed

    def set_state(self) -> None:
        """Toggles the target state of the device."""
        self.moving = True
        self.target_state = not self.state

    def get_state(self) -> bool:
        """Gets the current state of the device."""
        return self.state

    def update(self, time: SimTime, inputs) -> DeviceUpdate[Outputs]:
        """Run the update logic for the device.

        If the device is moving then the state of the device is updated.
        Otherwise nothing changes. In either case the current state of the
        device is returned.

        Args:
            time (SimTime): The time of the simulation in nanoseconds.
            inputs (dict): The dict containing the input values of state of the device.

        Returns:
            DeviceUpdate: A container for the Device's outputs and a callback time.
        """
        if self.moving:
            callback_period = SimTime(int(1e9 / self.speed))
            self.state = self.target_state
            self.moving = False
            return DeviceUpdate(
                self.Outputs(output=self.state),
                callback_period,
            )
        else:
            return DeviceUpdate(self.Outputs(output=self.state), None)


class PneumaticAdapter(EpicsAdapter):
    """An adapter for the Pneumatic class.

    Connects the device to an external messaging protocol.
    """

    device: PneumaticDevice
    db_file: Path

    def __init__(self, ioc_name: str, db_file: Path) -> None:  # noqa: D107
        super().__init__(ioc_name)
        self.db_file = db_file

    async def callback(self, value) -> None:
        """Set the state of the device and await a response.

        Args:
            value (bool): The value to set the state to.
        """
        self.device.set_state()
        await self.raise_interrupt()

    async def run_forever(
        self, device: Device, raise_interrupt: RaiseInterrupt
    ) -> None:  # noqa: D102
        await super().run_forever(device, raise_interrupt)
        EpicsAdapter.load_records(
            self.db_file, {"device": self.ioc_name}, remove_dtypes=True
        )
        builder.boolOut("FILTER", initial_value=False, on_update=self.callback)
        self.link_input_on_interrupt(
            builder.boolIn("FILTER_RBV"), self.device.get_state
        )
        self.build_ioc()
