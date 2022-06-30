from pathlib import Path

from softioc import builder

from tickit.adapters.epicsadapter import EpicsAdapter
from tickit.core.adapter import RaiseInterrupt
from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.compat.typing_compat import TypedDict


class FemtoDevice(Device):
    """Electronic signal amplifier."""

    #: An empty typed mapping of device inputs
    Inputs: TypedDict = TypedDict("Inputs", {"input": float})
    #: A typed mapping containing the current output value
    Outputs: TypedDict = TypedDict("Outputs", {"current": float})

    def __init__(
        self,
        initial_gain: float,
        initial_current: float,
    ) -> None:
        """Initialise the Femto device class.

        Args:
            initial_gain (Optional[float]): The initial amplified difference between \
                the input and output signals. Defaults to 2.5.
            initial_current (Optional[float]): The input signal current. \
                Defaults to 0.0.
        """
        self.gain: float = initial_gain
        self._current: float = initial_current

    def set_gain(self, gain: float) -> None:
        """Sets a new amplified difference between the input and output signals.

        Args:
            gain (float): The amplified difference between the input and output signals.
        """
        self.gain = gain

    def get_gain(self) -> float:
        """Returns the current amplified difference between the input and output signals.

        Returns:
            float: the amplified difference between the input and output signals.
        """
        return self.gain

    def set_current(self, input_current: float) -> None:
        """Set the output current based on the input current and the gain.

        The output current is calculated as:
            output_current = input_current * gain

        Args:
            input_current (float): The current of the input signal.
        """
        self._output_current = input_current * self.gain

    def get_current(self) -> float:
        """Returns the output current of the signal.

        Returns:
            float: The output current of the signal.
        """
        return self._output_current

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """Updates the state of the Femto device.

        Args:
            time (SimTime): The time of the simulation in nanoseconds.
            inputs (dict): The dict containing the input values of gain and current.

        Returns:
            DeviceUpdate: A container for the Device's outputs and a callback time.
        """
        current_value = inputs["input"]
        if current_value is not None:
            self.set_current(current_value)

        return DeviceUpdate(self.Outputs(current=self.get_current()), None)


class FemtoAdapter(EpicsAdapter):
    """The adapter for the Femto device."""

    device: FemtoDevice
    db_file: Path

    def __init__(self, ioc_name: str, db_file: Path) -> None:  # noqa: D107
        super().__init__(ioc_name)
        self.db_file = db_file

    async def run_forever(
        self, device: Device, raise_interrupt: RaiseInterrupt
    ) -> None:  # noqa: D102
        await super().run_forever(device, raise_interrupt)
        EpicsAdapter.load_records(
            self.db_file, {"device": self.ioc_name}, remove_dtypes=True
        )
        builder.aOut(
            "GAIN", initial_value=self.device.get_gain(), on_update=self.callback
        )
        self.link_input_on_interrupt(builder.aIn("GAIN_RBV"), self.device.get_gain)
        self.link_input_on_interrupt(builder.aIn("CURRENT"), self.device.get_current)
        self.build_ioc()

    async def callback(self, value) -> None:
        """Device callback function.

        Args:
            value (float): The value to set the gain to.
        """
        self.device.set_gain(value)
        await self.raise_interrupt()
