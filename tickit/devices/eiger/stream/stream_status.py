from dataclasses import dataclass, field, fields
from typing import Any, List

from tickit.devices.eiger.eiger_schema import ro_int, ro_str, ro_str_list


@dataclass
class StreamStatus:
    """Eiger stream status taken from the API spec."""

    state: str = field(default="ready", metadata=ro_str())
    error: List[str] = field(default_factory=lambda: [], metadata=ro_str_list())
    dropped: int = field(default=0, metadata=ro_int())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]
