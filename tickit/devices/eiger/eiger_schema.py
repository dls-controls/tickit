import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from typing import Any, Generic, List, Mapping, Optional, TypeVar

from apischema import serialized
from apischema.fields import with_fields_set
from apischema.metadata import skip
from apischema.serialization import serialize

T = TypeVar("T")

LOGGER = logging.getLogger(__name__)


def field_config(**kwargs) -> Mapping[str, Any]:
    """Helper function to create a typesafe dictionary.

    Helper function to create a typesafe dictionary to be inserted as
    dataclass metadata.

    Args:
        kwargs: Key/value pairs to go into the metadata

    Returns:
        Mapping[str, Any]: A dictionary of {key: value} where all keys are strings
    """
    return dict(**kwargs)


class AccessMode(Enum):
    """Possible access modes for field metadata."""

    READ_ONLY: str = "r"
    WRITE_ONLY: str = "w"
    READ_WRITE: str = "rw"


class ValueType(Enum):
    """Possible value types for field metadata."""

    FLOAT: str = "float"
    INT: str = "int"
    UINT: str = "uint"
    STRING: str = "string"
    STR_LIST: str = "string[]"
    BOOL: str = "bool"
    FLOAT_GRID: str = "float[][]"
    UINT_GRID: str = "uint[][]"
    DATE: str = "date"
    DATETIME: str = "datetime"
    NONE: str = "none"
    STATE: str = "State"


#
# Shortcuts to creating dataclass field metadata
#
rw_float: partial = partial(
    field_config, value_type=ValueType.FLOAT, access_mode=AccessMode.READ_WRITE
)
ro_float: partial = partial(
    field_config, value_type=ValueType.FLOAT, access_mode=AccessMode.READ_ONLY
)
rw_int: partial = partial(
    field_config, value_type=ValueType.INT, access_mode=AccessMode.READ_WRITE
)
ro_int: partial = partial(
    field_config, value_type=ValueType.INT, access_mode=AccessMode.READ_ONLY
)
rw_uint: partial = partial(
    field_config, value_type=ValueType.UINT, access_mode=AccessMode.READ_WRITE
)
rw_str: partial = partial(
    field_config, value_type=ValueType.STRING, access_mode=AccessMode.READ_WRITE
)
ro_str: partial = partial(
    field_config, value_type=ValueType.STRING, access_mode=AccessMode.READ_ONLY
)
rw_bool: partial = partial(
    field_config, value_type=ValueType.BOOL, access_mode=AccessMode.READ_WRITE
)
rw_float_grid: partial = partial(
    field_config,
    value_type=ValueType.FLOAT_GRID,
    access_mode=AccessMode.READ_WRITE,
)
rw_uint_grid: partial = partial(
    field_config,
    value_type=ValueType.UINT_GRID,
    access_mode=AccessMode.READ_WRITE,
)
ro_date: partial = partial(
    field_config, value_type=ValueType.DATE, access_mode=AccessMode.READ_ONLY
)
rw_datetime: partial = partial(
    field_config, value_type=ValueType.DATETIME, access_mode=AccessMode.READ_WRITE
)
rw_state: partial = partial(
    field_config, value_type=ValueType.STATE, access_mode=AccessMode.READ_WRITE
)
ro_str_list: partial = partial(
    field_config, value_type=ValueType.STR_LIST, access_mode=AccessMode.READ_ONLY
)


@with_fields_set
@dataclass
class Value(Generic[T]):
    """Schema for a value to be returned by the API. Most fields are optional."""

    value: T
    value_type: str
    access_mode: Optional[str] = None
    unit: Optional[str] = None
    min: Optional[T] = None
    max: Optional[T] = None
    allowed_values: Optional[List[str]] = None


def construct_value(obj, param):  # noqa: D103

    value = obj[param]["value"]
    meta = obj[param]["metadata"]

    if "allowed_values" in meta:
        data = serialize(
            Value(
                value,
                meta["value_type"].value,
                access_mode=meta["access_mode"].value,
                allowed_values=meta["allowed_values"],
            )
        )

    else:
        data = serialize(
            Value(
                value,
                meta["value_type"].value,
                access_mode=meta["access_mode"].value,
            )
        )

    return data


@dataclass
class SequenceComplete:
    """Schema for confirmation returned by operations that do not return values."""

    _sequence_id: int = field(default=1, metadata=skip, init=True, repr=False)

    @serialized("sequence id")  # type: ignore
    @property
    def sequence_id(self) -> int:  # noqa: D102
        return self._sequence_id
