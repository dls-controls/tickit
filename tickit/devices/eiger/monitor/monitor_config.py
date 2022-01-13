from dataclasses import dataclass, field, fields
from typing import Any

from tickit.devices.eiger.eiger_schema import rw_int, rw_str


@dataclass
class MonitorConfig:
    """Eiger monitor configuration taken from the API spec."""

    mode: str = field(
        default="enabled", metadata=rw_str(allowed_values=["enabled", "disabled"])
    )
    buffer_size: int = field(default=512, metadata=rw_int())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]

    def __setitem__(self, key: str, value: Any) -> None:  # noqa: D105
        self.__dict__[key] = value
