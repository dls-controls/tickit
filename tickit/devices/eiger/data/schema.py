import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Union

from zmq import Frame

Json = Dict[str, Any]
Sendable = Union[bytes, Frame, memoryview]
MultipartMessage = Iterable[Sendable]


def fmt_json(j: Json):  # noqa: D103
    return json.dumps(j).encode("utf_8")


@dataclass
class HeadedBlob:
    """Blob object for frame header."""

    header: Json
    blob: bytes

    def to_message(self) -> MultipartMessage:  # noqa: D102
        yield fmt_json(self.header)
        yield self.blob


@dataclass
class ImageBlob(HeadedBlob):
    """Blob object for frame data."""

    dimensions: Json
    times: Json

    def to_message(self) -> MultipartMessage:  # noqa: D102
        yield fmt_json(self.header)
        yield fmt_json(self.dimensions)
        yield self.blob
        yield fmt_json(self.times)


@dataclass
class Header:
    """Class for header json."""

    global_header: Json
    global_header_config: Json

    flat_field: Optional[HeadedBlob] = None
    pixel_mask: Optional[HeadedBlob] = None
    countrate: Optional[HeadedBlob] = None

    def to_message(self) -> MultipartMessage:  # noqa: D102
        yield fmt_json(self.global_header)
        yield fmt_json(self.global_header_config)

        details = [self.flat_field, self.pixel_mask, self.countrate]
        for detail in details:
            if detail:
                yield from detail.to_message()
