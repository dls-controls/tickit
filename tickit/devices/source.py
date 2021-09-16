import logging
from typing import Any

from tickit.core.device import ConfigurableDevice, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.utils.compat.typing_compat import TypedDict

LOGGER = logging.getLogger(__name__)


class Source(ConfigurableDevice):
    """A simple device which produces a pre-configured value"""

    #: An empty typed mapping of device inputs
    Inputs: TypedDict = TypedDict("Inputs", {})
    #: A typed mapping containing the 'value' output value
    Outputs: TypedDict = TypedDict("Outputs", {"value": Any})

    def __init__(self, value: Any) -> None:
        """A constructor of the source, which takes the pre-configured value

        Args:
            value (Any): A pre-configured output value
        """
        self.value = value

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """The update method which produces the pre-configured value

        Args:
            time (SimTime): The current simulation time (in nanoseconds)
            inputs (State): A mapping of inputs to the device and their values

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the pre-configured value, and
                never requests a callback
        """

        LOGGER.debug("Sourced {}".format(self.value))
        return DeviceUpdate(Source.Outputs(value=self.value), None)