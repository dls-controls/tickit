import asyncio
import logging
import struct
from typing import Optional

import pytest
from pint.quantity import Quantity
from pytest import approx

from tickit.core.device import DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.devices.cryostream.base import cK
from tickit.devices.cryostream.cryostream import CryostreamDevice
from tickit.devices.cryostream.states import PhaseIds
from tickit.devices.cryostream.status import ExtendedStatus

# # # # # Cryostream Tests # # # # #


@pytest.fixture
def cryostream() -> CryostreamDevice:
    return CryostreamDevice()


def test_cryostream_constructor():
    CryostreamDevice()


def test_cryostream_update_hold(cryostream):
    starting_temperature = cryostream.get_gas_temp()
    device_update: DeviceUpdate = cryostream.update(time=SimTime(1e9), inputs={})
    device_update.outputs["temperature"] == starting_temperature


@pytest.mark.asyncio
async def test_cryostream_update_cool(cryostream: CryostreamDevice):
    starting_temperature = cryostream.gas_temp
    target_temperature = starting_temperature - 50 * cK
    await cryostream.cool(target_temperature.magnitude)

    time = SimTime(0)
    device_update: DeviceUpdate
    while cryostream.phase_id != PhaseIds.HOLD.value:
        logging.info(f"Running time step: {time}")
        device_update = cryostream.update(time, inputs={})
        time_update: Optional[SimTime] = device_update.call_at

        if time_update is None:
            time = SimTime(int(time) + int(1e9))
            continue
        else:
            time = time_update

    max_diff = 10
    assert device_update.outputs["temperature"] == approx(
        target_temperature, abs=max_diff
    )


@pytest.mark.asyncio
async def test_cryostream_update_end(cryostream: CryostreamDevice):
    starting_temperature: Quantity = cryostream.default_temp_shutdown - 100 * cK
    cryostream.gas_temp = starting_temperature
    await cryostream.end(cryostream.default_ramp_rate)
    assert cryostream.phase_id == PhaseIds.RAMP.value
    assert cryostream.gas_flow == 5

    time = SimTime(0)
    device_update: DeviceUpdate
    while cryostream.phase_id != PhaseIds.HOLD.value:
        logging.info(f"Running time step: {time}")
        device_update = cryostream.update(time, inputs={})
        time_update: Optional[SimTime] = device_update.call_at

        if time_update is None:
            continue
        else:
            time = time_update

    max_diff = 10
    target_temp = cryostream.default_temp_shutdown.magnitude
    assert device_update.outputs["temperature"] == approx(target_temp, abs=max_diff)


@pytest.mark.asyncio
async def test_cryostream_update_plat(cryostream: CryostreamDevice):
    starting_temperature: int = cryostream.gas_temp.magnitude
    await cryostream.plat(5)
    assert cryostream.phase_id == PhaseIds.PLAT.value

    time = SimTime(0)
    time_update: Optional[SimTime] = time
    device_update: DeviceUpdate
    while time_update is not None:
        logging.info(f"Running time step: {time}")
        device_update = cryostream.update(time, inputs={})
        time_update = device_update.call_at

        if time_update is None:
            continue
        else:
            time = time_update

    assert device_update.outputs["temperature"] == starting_temperature


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tickit_task", ["examples/configs/cryo-tcp.yaml"], indirect=True
)
async def test_cryostream_system(tickit_task):
    reader, writer = await asyncio.open_connection("localhost", 25565)

    async def write(data: bytes):
        writer.write(data)
        await writer.drain()

    async def get_status() -> ExtendedStatus:
        return ExtendedStatus.from_packed(await reader.read(42))

    # Check we start at 300K
    status = await get_status()
    assert status.gas_temp == 30000
    assert status.turbo_mode == 0
    # Start a ramp
    await write(b"\x06\x0b" + struct.pack(">HH", 360, 30030))
    # Check we go to to 300.3K, eventually
    status = await get_status()
    assert status.gas_temp == pytest.approx(30015, rel=5)
    status = await get_status()
    assert status.gas_temp == pytest.approx(30025, rel=5)
    status = await get_status()
    assert status.gas_temp == pytest.approx(30030, rel=5)
    # Turbo on
    await write(b"\x03\x14\x01")
    status = await get_status()
    assert status.gas_temp == pytest.approx(30030, rel=5)
    assert status.turbo_mode == 1
    # Cool to 300K
    await write(b"\x04\x0e" + struct.pack(">H", 30000))
    status = await get_status()
    assert status.gas_temp == pytest.approx(30000, rel=5)
