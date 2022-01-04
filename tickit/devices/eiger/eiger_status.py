from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, List

from .eiger_schema import ro_str_list, rw_datetime, rw_float, rw_state


class State(Enum):
    """Possible states of the Eiger detector."""

    NA = "na"
    READY = "ready"
    INITIALIZE = "initialize"
    CONFIGURE = "configure"
    ACQUIRE = "acquire"
    IDLE = "idle"
    TEST = "test"
    ERROR = "error"


@dataclass
class EigerStatus:
    """Stores the status parameters of the Eiger detector."""

    state: State = field(
        default=State.NA,
        metadata=rw_state(allowed_values=[state.value for state in State]),
    )
    errors: List[str] = field(default_factory=list, metadata=ro_str_list())
    th0_temp: float = field(default=24.5, metadata=rw_float())
    th0_humidity: float = field(default=0.2, metadata=rw_float())
    time: datetime = field(default=datetime.now(), metadata=rw_datetime())
    dcu_buffer_free: float = field(default=0.5, metadata=rw_float())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]
