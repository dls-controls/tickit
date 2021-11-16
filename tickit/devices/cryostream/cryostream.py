import asyncio
import struct
from typing import AsyncIterable

from tickit.adapters.composed import ComposedAdapter
from tickit.adapters.interpreters.command import CommandInterpreter, RegexCommand
from tickit.adapters.servers.tcp import TcpServer
from tickit.core.device import DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.devices.cryostream.base import CryostreamBase
from tickit.devices.cryostream.states import PhaseIds
from tickit.utils.byte_format import ByteFormat
from tickit.utils.compat.typing_compat import TypedDict

_EXTENDED_STATUS = ">BBHHHBBHHHHHBBBBBBHHBBBBBBBBHH"


class CryostreamDevice(CryostreamBase):
    """A Cryostream device, used for cooling of samples using cold gas."""

    #: An empty typed mapping of device inputs
    Inputs: TypedDict = TypedDict("Inputs", {})
    #: A typed mapping containing the 'temperature' output value
    Outputs: TypedDict = TypedDict("Outputs", {"temperature": float})

    def __init__(self) -> None:
        """A Cryostream constructor sets up initial internal values."""
        super().__init__()
        self.phase_id: int = PhaseIds.HOLD.value
        self.callback_period: SimTime = SimTime(int(1e9))

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """The update method which changes the output temperature according to set modes.

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the value of the output
                temperature, and requests callback if temperature should continue to
                change.
        """
        if self.phase_id in (PhaseIds.RAMP.value, PhaseIds.COOL.value):
            new_temperature: int = self.update_temperature(time)
            self.set_gas_temp(new_temperature)
            return DeviceUpdate(
                self.Outputs(temperature=self.get_gas_temp()),
                SimTime(time + self.callback_period),
            )
        if self.phase_id == PhaseIds.PLAT.value:
            self.phase_id = PhaseIds.HOLD.value
            return DeviceUpdate(
                self.Outputs(temperature=self.get_gas_temp()),
                SimTime(time + int(self.plat_duration * 1e10)),
            )
        return DeviceUpdate(self.Outputs(temperature=self.get_gas_temp()), None)


class CryostreamAdapter(ComposedAdapter):
    """A Cryostream TCP adapter which sends regular status packets and can set modes."""

    device: CryostreamDevice

    def __init__(
        self,
        host: str = "localhost",
        port: int = 25565,
    ) -> None:
        """A CryostreamAdapter constructor which instantiates a TcpServer with host and port.

        Args:
            device (Device): The device which this adapter is attached to
            raise_interrupt (Callable): A callback to request that the device is
                updated immediately.
            host (Optional[str]): The host address of the TcpServer. Defaults to
                "localhost".
            port (Optional[int]): The bound port of the TcpServer. Defaults to 25565.
        """
        super().__init__(
            TcpServer(format=ByteFormat(b"%b"), host=host, port=port),
            CommandInterpreter(),
        )

    async def on_connect(self) -> AsyncIterable[bytes]:
        """A method which continiously yields status packets.

        Returns:
            AsyncIterable[bytes]: An asyncronous iterable of packed Cryostream status
                packets.
        """
        while True:
            await asyncio.sleep(2.0)
            await self.device.set_status_format(1)
            status = await self.device.get_status(1)
            yield status.pack()

    @RegexCommand(b"\\x02\\x0a", interrupt=True)
    async def restart(self) -> None:
        """A regex bytes command which restarts the Cryostream."""
        await self.device.restart()

    @RegexCommand(b"\\x02\\x0d", interrupt=True)
    async def hold(self) -> None:
        """A regex bytes command which holds the current temperature."""
        await self.device.hold()

    @RegexCommand(b"\\x02\\x10", interrupt=True)
    async def purge(self) -> None:
        """A regex bytes command which purges (immediately raise to 300K)."""
        await self.device.purge()

    @RegexCommand(b"\\x02\\x11", interrupt=True)
    async def pause(self) -> None:
        """A regex bytes command which pauses."""
        await self.device.pause()

    @RegexCommand(b"\\x02\\x12", interrupt=True)
    async def resume(self) -> None:
        """A regex bytes command which resumes the last command."""
        await self.device.resume()

    @RegexCommand(b"\\x02\\x13", interrupt=True)
    async def stop(self) -> None:
        """A regex bytes command which stops gas flow."""
        await self.device.stop()

    @RegexCommand(b"\\x03\\x14([\\x00\\x01])", interrupt=True)
    async def turbo(self, turbo_on: bytes) -> None:
        """A regex bytes command which enables / disables turbo mode.

        Args:
            turbo_on (bytes): The desired turbo mode, where 0 denotes off and 1 denotes
                on.
        """
        turbo_on = struct.unpack(">B", turbo_on)[0]
        await self.device.turbo(turbo_on)

    # Todo set status format not interrupt
    @RegexCommand(b"\\x03\\x28([\\x00\\x01])", interrupt=False)
    async def set_status_format(self, status_format: bytes) -> None:
        """A regex bytes command which sets the status packet format.

        Args:
            status_format (bytes): The status packet format, where 0 denotes a standard
                status packet and 1 denotes an extended status packet.
        """
        status_format = struct.unpack(">B", status_format)[0]
        await self.device.set_status_format(status_format)

    @RegexCommand(b"\\x04\\x0c(.{2})", interrupt=True)
    async def plat(self, duration: bytes) -> None:
        """A regex bytes command which maintains temperature for a set amount of time.

        Args:
            duration (bytes): The duration for which the temperature should be held.
        """
        duration = struct.unpack(">H", duration)[0]
        await self.device.plat(duration)

    @RegexCommand(b"\\x04\\x0f(.{2})", interrupt=True)
    async def end(self, ramp_rate: bytes) -> None:
        """A regex bytes command which brings the gas temperature to 300 K at ramp rate.

        Args:
            ramp_rate (bytes): The rate at which the temperature should change.
        """
        ramp_rate = struct.unpack(">H", ramp_rate)[0]
        await self.device.end(ramp_rate)

    @RegexCommand(b"\\x04\\x0e(.{2})", interrupt=True)
    async def cool(self, target_temp: bytes) -> None:
        """A regex bytes command which makes decreases temperature to a set value.

        Args:
            target_temp (bytes): The target temperature.
        """
        target_temp = struct.unpack(">H", target_temp)[0]
        await self.device.cool(target_temp)

    @RegexCommand(b"\\x06\\x0b(.{2,4})", interrupt=True)
    async def ramp(self, values: bytes) -> None:
        """Change gas temperature to a set value at a controlled rate.

        Args:
            values (bytes): The rate at which the temperature should change and the
                target temperature.
        """
        ramp_rate, target_temp = struct.unpack(">HH", values)
        await self.device.ramp(ramp_rate, target_temp)
