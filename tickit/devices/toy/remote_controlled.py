import asyncio
import struct
from typing import AsyncIterable

from tickit.adapters.composed import ComposedAdapter
from tickit.adapters.interpreters.regex_command import RegexInterpreter
from tickit.core.device import ConfigurableDevice, UpdateEvent
from tickit.core.typedefs import SimTime, State
from tickit.utils.compat.typing_compat import TypedDict


class RemoteControlled(ConfigurableDevice):
    Output = TypedDict("Output", {"observed": float})

    def __init__(
        self,
        initial_observed: float = 0,
        initial_unobserved: float = 42,
        initial_hidden: float = 3.14,
    ) -> None:
        self.observed = initial_observed
        self.unobserved = initial_unobserved
        self.hidden = initial_hidden

    def update(self, time: SimTime, inputs: State) -> UpdateEvent:
        return UpdateEvent(RemoteControlled.Output(observed=self.observed), None)


class RemoteControlledAdapter(ComposedAdapter):
    _interpreter = RegexInterpreter()
    _device: RemoteControlled

    async def on_connect(self) -> AsyncIterable[bytes]:
        while True:
            await asyncio.sleep(5.0)
            yield "U is {}".format(self._device.unobserved).encode("utf-8")

    @_interpreter.command(b"\x01")
    async def get_observed_bytes(self) -> bytes:
        return struct.pack(">i", self._device.observed)

    @_interpreter.command(r"O", format="utf-8")
    async def get_observed_str(self) -> bytes:
        return str(self._device.observed).encode("utf-8")

    @_interpreter.command(b"\x01(.{4})", interrupt=True)
    async def set_observed_bytes(self, value: bytes) -> bytes:
        self._device.observed = struct.unpack(">i", value)[0]
        return struct.pack(">i", self._device.observed)

    @_interpreter.command(r"O=(\d+\.?\d*)", interrupt=True, format="utf-8")
    async def set_observed_str(self, value: int) -> bytes:
        self._device.observed = value
        return "Observed set to {}".format(self._device.observed).encode("utf-8")

    @_interpreter.command(b"\x02")
    async def get_unobserved_bytes(self) -> bytes:
        return struct.pack(">i", self._device.unobserved)

    @_interpreter.command(r"U", format="utf-8")
    async def get_unobserved_str(self) -> bytes:
        return str(self._device.unobserved).encode("utf-8")

    @_interpreter.command(b"\x02(.{4})", interrupt=True)
    async def set_unobserved_bytes(self, value: bytes) -> bytes:
        self._device.unobserved = struct.unpack(">i", value)[0]
        return struct.pack(">i", self._device.unobserved)

    @_interpreter.command(r"U=(\d+\.?\d*)", format="utf-8")
    async def set_unobserved_str(self, value: int) -> bytes:
        self._device.unobserved = value
        return "Unobserved set to {}".format(self._device.unobserved).encode("utf-8")

    @_interpreter.command(chr(0x1F95A), format="utf-8")
    async def misc(self) -> bytes:
        return chr(0x1F430).encode("utf-8")

    @_interpreter.command(r"H=(\d+\.?\d*)", format="utf-8")
    async def set_hidden(self, value: float) -> None:
        print("Hidden set to {}".format(self._device.hidden))

    @_interpreter.command(r"H", format="utf-8")
    async def get_hidden(self) -> None:
        pass

    @_interpreter.command(r"O\?(\d+)", format="utf-8")
    async def yield_observed(self, n: int = 10) -> AsyncIterable[bytes]:
        for i in range(1, int(n)):
            await asyncio.sleep(1.0)
            yield "Observed is {}".format(self._device.observed).encode("utf-8")