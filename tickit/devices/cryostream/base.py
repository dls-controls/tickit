import logging
from ctypes import c_short, c_ubyte, c_ushort
from typing import Union

from pint import UnitRegistry
from pint.quantity import Quantity

from tickit.devices.cryostream.states import AlarmCodes, PhaseIds, RunModes
from tickit.devices.cryostream.status import ExtendedStatus, Status

LOGGER = logging.getLogger(__name__)

unit_registry = UnitRegistry()
cK = unit_registry.centikelvin
liters_per_minute = unit_registry.liters / unit_registry.minute


class CryostreamBase:
    """A base class for cryostream device logic."""

    min_temp: Quantity = 8000 * cK
    max_temp: Quantity = 40000 * cK
    min_rate: int = 1
    max_rate: int = 360
    min_plat_duration: int = 1
    max_plat_duration: int = 1440
    default_temp_shutdown: Quantity = 30000 * cK
    default_ramp_rate: int = 360
    random_value: int = 20  # for status packet unknown values

    def __init__(self) -> None:
        """A CryostreamBase constructor which assigns initial values."""
        self.run_mode: int = 0
        self.phase_id: int = 0
        self.alarm_code: int = 0
        self.turbo_mode: int = 0
        self.gas_temp: Quantity = 30000 * cK
        self.ramp_rate: int = 0
        self.gas_flow: int = 0
        self._target_temp: Quantity = 0 * cK
        self.time_at_last_update: float = 0.0

    async def restart(self) -> None:
        """Stop Cryostream and re-initialise system back to Ready."""
        start_target_temp = 10000
        await self.stop()
        self.run_mode = RunModes.STARTUP.value
        await self.cool(start_target_temp)
        if self.gas_temp == start_target_temp:
            self.run_mode = RunModes.STARTUPOK.value
        else:
            self.run_mode = RunModes.STARTUPFAIL.value

    async def ramp(self, ramp_rate: int, target_temp: int) -> None:
        """Change gas temperature to a set value at a controlled rate.

        Args:
            ramp_rate (int): The rate at which the temperature should change.
            target_temp (int): The target temperature.
        """
        target_temp_cK: Quantity = target_temp * cK
        if ramp_rate < self.min_rate or ramp_rate > self.max_rate:
            self.alarm_code = AlarmCodes.TEMP_CONTROL_ERROR
        else:
            self.ramp_rate = ramp_rate

        if target_temp_cK < self.min_temp or target_temp_cK > self.max_temp:
            self.alarm_code = AlarmCodes.TEMP_CONTROL_ERROR
        else:
            self._target_temp = target_temp_cK

        # Todo
        """
        difference_temp = abs(self.gas_temp - self.target_temp)
        if 10 < difference_temp < 25:
            self.alarm_code = AlarmCodes.TEMP_WARNING
        if difference_temp > 25:
            self.alarm_code = AlarmCodes.TEMP_CONTROL_ERROR
        """

        self.run_mode = RunModes.RUN.value
        if self.phase_id != PhaseIds.COOL.value:
            self.phase_id = PhaseIds.RAMP.value

        if (
            self.phase_id == PhaseIds.COOL.value
            or (self.turbo_mode == 1 and self._target_temp < 31000 * cK)
            or self._target_temp < 9000 * cK
        ):
            self.gas_flow = 10
        else:
            self.gas_flow = 5

    async def plat(self, duration: int) -> None:
        """Maintain the current temperature for a set amount of time.

        Args:
            duration (int): The duration for which the temperature should be held.
        """
        if duration < self.min_plat_duration:

            raise ValueError("Duration set to less than minimum plat duration.")
        if duration > self.max_plat_duration:
            raise ValueError("Duration set to more than maximum plat duration.")

        self.plat_duration = duration
        self._target_temp = self.gas_temp
        self.run_mode = RunModes.RUN.value
        self.phase_id = PhaseIds.PLAT.value

    async def hold(self) -> None:
        """Maintain the current temperature indefinitely."""
        self.run_mode = RunModes.RUN.value
        self.phase_id = PhaseIds.HOLD.value
        self._target_temp = self.gas_temp

    async def cool(self, target_temp: int) -> None:
        """Make gas temperature decrease to a set value as quickly as possible.

        Args:
            target_temp (int): The target temperature.
        """
        self.run_mode = RunModes.RUN
        self.phase_id = PhaseIds.COOL.value
        await self.ramp(self.default_ramp_rate, target_temp)

    async def end(self, ramp_rate: int) -> None:
        """Bring the gas temperature to 300 K at ramp rate, then halt and stop.

        Args:
            ramp_rate (int): The rate at which the temperature should change.
        """
        if self.run_mode not in (
            RunModes.SHUTDOWNOK.value,
            RunModes.SHUTDOWNFAIL.value,
        ):
            self.phase_id = PhaseIds.END.value
            await self.ramp(ramp_rate, self.default_temp_shutdown.magnitude)
            if self.gas_temp == self.default_temp_shutdown:
                self.gas_flow = 0
                self.run_mode = RunModes.SHUTDOWNOK.value
            else:
                self.run_mode = RunModes.SHUTDOWNFAIL.value

    async def purge(self) -> None:
        """Bring the gas temperature to 300 K at max rate, then halt and stop."""
        if self.run_mode not in (
            RunModes.SHUTDOWNOK.value,
            RunModes.SHUTDOWNFAIL.value,
        ):
            self.phase_id = PhaseIds.PURGE.value
            self.gas_flow = 0
            await self.ramp(
                self.default_ramp_rate, self.default_temp_shutdown.magnitude
            )
            self.phase_id = PhaseIds.PURGE.value
            if self.gas_temp == self.default_temp_shutdown:
                self.run_mode = RunModes.SHUTDOWNOK.value
            else:
                self.run_mode = RunModes.SHUTDOWNFAIL.value

    async def pause(self) -> None:
        """Interrupt and maintain the current gas temperature until resumed."""
        # TODO interrupt other commands from running
        ...

    async def resume(self) -> None:
        """Resume the previous command."""
        if self.phase_id == PhaseIds.HOLD.value:
            LOGGER.warn("Cannot return to previous command")  # TODO keep commands

    async def stop(self) -> None:
        """Gas flow is halted and the system is stopped at the current temperature."""
        if self.run_mode not in (
            RunModes.SHUTDOWNOK.value,
            RunModes.SHUTDOWNFAIL.value,
        ):
            self.gas_flow = 0
            self._target_temp = self.gas_temp
            self.run_mode = RunModes.SHUTDOWNOK.value

    async def turbo(self, turbo_on: int) -> None:
        """Set turbo mode to use maximum achievable flow.

        The system will use 10 l/min gas flow except above 310 K
        Above 310 K available heater power limits the maximum achievable
        flow to 5 l/min.

        Args:
            turbo_on (int): The desired turbo mode, where 0 denotes off and 1 denotes
                on.
        """
        if turbo_on == 1:
            self.turbo_mode = 1
            if self.gas_temp < (310 * cK):
                self.gas_flow = 10
            else:
                self.gas_flow = 5
        else:
            self.turbo_mode = 0

    def update_temperature(self, time: float) -> int:
        """Update the Cryostream gas temperature according to mode and time.

        Args:
            time (float): The current simulation time (in nanoseconds).

        Returns:
            int: The current gas temperature.
        """
        delta_time = (time - self.time_at_last_update) / 1e9
        difference = self._target_temp - self.gas_temp
        if abs(self.gas_temp - self._target_temp) < (10 * cK):
            self.phase_id = PhaseIds.HOLD.value
        delta_temp = (self.gas_flow * delta_time) * cK
        if difference < 0:
            delta_temp = -delta_temp
        self.gas_temp = self.gas_temp + delta_temp
        self.time_at_last_update = time

        return int(self.gas_temp.magnitude)

    async def set_status_format(self, status_format: int) -> None:
        """Sets the status packet format.

        Args:
            status_format (int): The status packet format, where 0 denotes a standard
                status packet and 1 denotes an extended status packet.
        """
        if status_format == 0:
            self.status = Status(
                length=c_ubyte(32).value,  # 0R
                type_status=c_ubyte(1).value,  # 0R
                gas_set_point=c_ushort(22).value,  # 02R
                gas_temp=c_ushort(22).value,  # 02r
                gas_error=c_short(22).value,
                run_mode=c_ubyte(self.run_mode).value,
                phase_id=c_ubyte(self.phase_id).value,
                ramp_rate=c_short(self.ramp_rate).value,
                target_temp=c_ushort(self._target_temp.magnitude).value,
                evap_temp=c_ushort(22).value,
                suct_temp=c_ushort(22).value,
                remaining=c_ushort(88).value,
                gas_flow=c_ubyte(self.gas_flow).value,
                gas_heat=c_ubyte(22).value,
                evap_heat=c_ubyte(22).value,
                suct_heat=c_ubyte(22).value,
                line_pressure=c_ubyte(10).value,
                alarm_code=c_ubyte(self.alarm_code).value,
                run_time=c_ushort(100).value,
                controller_number=c_ushort(10).value,
                software_version=c_ubyte(12).value,
                evap_adjust=c_ubyte(120).value,
            )

        if status_format == 1:
            self.extended_status = ExtendedStatus(
                length=c_ubyte(42).value,
                type_status=c_ubyte(2).value,
                gas_set_point=c_ushort(22).value,
                gas_temp=c_ushort(22).value,
                gas_error=c_short(22).value,
                run_mode=c_ubyte(self.run_mode).value,
                phase_id=c_ubyte(self.phase_id).value,
                ramp_rate=c_short(self.ramp_rate).value,
                target_temp=c_ushort(self._target_temp.magnitude).value,
                evap_temp=c_ushort(22).value,
                suct_temp=c_ushort(22).value,
                remaining=c_ushort(88).value,
                gas_flow=c_ubyte(self.gas_flow).value,
                gas_heat=c_ubyte(22).value,
                evap_heat=c_ubyte(22).value,
                suct_heat=c_ubyte(22).value,
                line_pressure=c_ubyte(10).value,
                alarm_code=c_ubyte(self.alarm_code).value,
                run_time=c_ushort(100).value,
                controller_number=c_ushort(10).value,
                software_version=c_ubyte(12).value,
                evap_adjust=c_ubyte(120).value,
                turbo_mode=c_ubyte(self.turbo_mode).value,
                hardware_type=c_ubyte(1).value,
                shutter_state=c_ubyte(22).value,
                shutter_time=c_ubyte(22).value,
                avg_gas_heat=c_ubyte(22).value,
                avg_suct_heat=c_ubyte(22).value,
                time_to_fill=c_ushort(22).value,
                total_hours=c_ushort(22).value,
            )
            self.extended_status.gas_temp = c_ushort(int(self.gas_temp.magnitude)).value
            self.extended_status.run_mode = c_ubyte(self.run_mode).value
            self.extended_status.phase_id = c_ubyte(self.phase_id).value
            self.extended_status.target_temp = c_ushort(
                int(self._target_temp.magnitude)
            ).value
            self.extended_status.ramp_rate = c_short(self.ramp_rate).value
            self.extended_status.gas_flow = c_ubyte(self.gas_flow).value
            self.extended_status.alarm_code = c_ubyte(self.alarm_code).value
            self.extended_status.turbo_mode = c_ubyte(self.turbo_mode).value

    async def get_status(self, status_format: int) -> Union[Status, ExtendedStatus]:
        """Get a Status or ExtendedStatus packet.

        Args:
            status_format (int): The status packet format, where 0 denotes a standard
                status packet and 1 denotes an extended status packet.

        Returns:
            Union[
                tickit.devices.cryostream.status.Status,
                tickit.devices.cryostream.status.ExtendedStatus]: The status packet.
        """
        if status_format == 0:
            if hasattr(self, "status"):
                pass
            else:
                await self.set_status_format(0)

            return self.status

        if status_format == 1:
            if hasattr(self, "extended_status"):
                pass
            else:
                await self.set_status_format(1)

            return self.extended_status

        else:
            raise ValueError("Invalid status format parameter.")

    def set_gas_temp(self, gas_temp: int) -> None:
        """Set the gas temperature of the device. For testing purposes only."""
        self.gas_temp = gas_temp * cK

    def get_gas_temp(self) -> int:
        """Get the gas temperature of the device.

        Returns the gas temperature as an integer (value is stored as a pint.Quantity).
        """
        return int(self.gas_temp.magnitude)
