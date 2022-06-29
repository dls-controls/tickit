from dataclasses import dataclass
from pathlib import Path

from tickit.core.components.component import Component, ComponentConfig
from tickit.core.components.device_simulation import DeviceSimulation

from .pneumatic import PneumaticAdapter, PneumaticDevice


@dataclass
class Pneumatic(ComponentConfig):
    """Pneumatic simulation with EPICS IOC adapter."""

    initial_speed: float = 2.5
    initial_state: bool = False
    db_file: Path = Path("tickit/devices/pneumatic/db_files/filter1.db")
    ioc_name: str = "PNEUMATIC"

    def __call__(self) -> Component:  # noqa: D102
        return DeviceSimulation(
            name=self.name,
            device=PneumaticDevice(
                initial_speed=self.initial_speed, initial_state=self.initial_state
            ),
            adapters=[PneumaticAdapter(db_file=self.db_file, ioc_name=self.ioc_name)],
        )
