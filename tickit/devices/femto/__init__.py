from dataclasses import dataclass
from pathlib import Path

from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_simulation import DeviceSimulation

from .current import CurrentDevice
from .femto import FemtoAdapter, FemtoDevice


@dataclass
class Femto(ComponentConfig):
    """Femto simulation with EPICS IOC."""

    initial_gain: float = 2.5
    initial_current: float = 0.0
    db_file: Path = Path("tickit/devices/femto/record.db")
    ioc_name: str = "FEMTO"

    def __call__(self) -> Component:  # noqa: D102
        return DeviceSimulation(
            name=self.name,
            device=FemtoDevice(
                initial_gain=self.initial_gain, initial_current=self.initial_current
            ),
            adapters=[FemtoAdapter(db_file=self.db_file, ioc_name=self.ioc_name)],
        )


@dataclass
class Current(ComponentConfig):
    """Simulated current source."""

    callback_period: int = int(1e9)

    def __call__(self) -> Component:  # noqa: D102
        return DeviceSimulation(
            name=self.name,
            device=CurrentDevice(callback_period=self.callback_period),
        )
