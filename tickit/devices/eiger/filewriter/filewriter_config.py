from dataclasses import dataclass, field, fields
from typing import Any

from tickit.devices.eiger.eiger_schema import rw_bool, rw_int, rw_str


@dataclass
class FileWriterConfig:
    """Eiger filewriter configuration taken from the API spec."""

    mode: str = field(
        default="enabled", metadata=rw_str(allowed_values=["enabled", "disabled"])
    )
    nimages_per_file: int = field(default=1, metadata=rw_int())
    image_nr_start: int = field(default=0, metadata=rw_int())
    name_pattern: str = field(default="test.h5", metadata=rw_str())
    compression_enabled: bool = field(default=False, metadata=rw_bool())

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
