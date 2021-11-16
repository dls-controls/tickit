from contextlib import nullcontext as does_not_raise
from random import getrandbits
from typing import Any, Dict

import pytest
from mock import Mock

from tickit.devices.cryostream.base import CryostreamBase, cK
from tickit.devices.cryostream.states import AlarmCodes, PhaseIds, RunModes
from tickit.devices.cryostream.status import ExtendedStatus, Status


def rand_bool() -> bool:
    return bool(getrandbits(1))


@pytest.mark.asyncio
async def test_restart():
    cryostream_base = CryostreamBase()
    await cryostream_base.restart()
    assert cryostream_base.run_mode in (
        RunModes.STARTUPOK.value,
        RunModes.STARTUPFAIL.value,
    )


@pytest.mark.parametrize(
    "test_params",
    [
        pytest.param(
            {
                "starting_temperature": 10000,
                "target_temperature": 9000,
                "ramp_rate": 360,
                "expected_phase_id": PhaseIds.RAMP.value,
                "expected_alarm_code": AlarmCodes.NO_ERRORS.value,
                "expected_gas_flow": 5,
            },
            id="normal params",
        ),
        pytest.param(
            {
                "starting_temperature": 8999,
                "target_temperature": 8000,
                "ramp_rate": 360,
                "expected_phase_id": PhaseIds.RAMP.value,
                "expected_alarm_code": AlarmCodes.NO_ERRORS.value,
                "expected_gas_flow": 10,
            },
            id="gas gas gas",
        ),
        pytest.param(
            {
                "starting_temperature": 10000 * cK,
                "target_temperature": 90001,
                "ramp_rate": 360,
                "expected_phase_id": PhaseIds.RAMP.value,
                "expected_alarm_code": AlarmCodes.TEMP_CONTROL_ERROR.value,
                "expected_gas_flow": 10,
            },
            id="target temperature too high",
        ),
        pytest.param(
            {
                "starting_temperature": 10000 * cK,
                "target_temperature": 9000,
                "ramp_rate": 361,
                "expected_phase_id": PhaseIds.RAMP.value,
                "expected_alarm_code": AlarmCodes.TEMP_CONTROL_ERROR.value,
                "expected_gas_flow": 5,
            },
            id="ramp rate too high",
        ),
    ],
)
@pytest.mark.asyncio
async def test_ramp(test_params):
    cryostream_base = CryostreamBase()
    cryostream_base.gas_temp = test_params["starting_temperature"]

    await cryostream_base.ramp(
        ramp_rate=test_params["ramp_rate"],
        target_temp=test_params["target_temperature"],
    )

    assert cryostream_base.run_mode == RunModes.RUN.value
    assert cryostream_base.alarm_code == test_params["expected_alarm_code"]
    assert cryostream_base.phase_id == test_params["expected_phase_id"]
    assert cryostream_base.gas_flow == test_params["expected_gas_flow"]


@pytest.mark.parametrize(
    "test_params",
    [
        pytest.param(
            {
                "duration": 1440,
                "expected_phase_id": PhaseIds.PLAT.value,
                "expected_run_mode": RunModes.RUN.value,
                "raises": does_not_raise(),
            },
            id="normal params",
        ),
        pytest.param(
            {
                "duration": 0,
                "expected_phase_id": None,
                "expected_run_mode": None,
                "raises": pytest.raises(ValueError),
            },
            id="zero duration",
        ),
        pytest.param(
            {
                "duration": 1441,
                "expected_phase_id": None,
                "expected_run_mode": None,
                "raises": pytest.raises(ValueError),
            },
            id="too long",
        ),
    ],
)
@pytest.mark.asyncio
async def test_plat(test_params):
    cryostream_base = CryostreamBase()
    initial_run_mode = cryostream_base.run_mode
    initial_phase_id = cryostream_base.phase_id
    with test_params["raises"]:
        await cryostream_base.plat(test_params["duration"])

    if test_params["expected_phase_id"] is None:
        assert cryostream_base.phase_id == initial_phase_id
    else:
        assert cryostream_base.phase_id == test_params["expected_phase_id"]

    if test_params["expected_run_mode"] is None:
        assert cryostream_base.run_mode == initial_run_mode
    else:
        assert cryostream_base.run_mode == test_params["expected_run_mode"]


@pytest.mark.asyncio
async def test_hold():
    cryostream_base = CryostreamBase()
    cryostream_base.gas_temp = 2800 * cK
    await cryostream_base.hold()
    final_temperature = cryostream_base.update_temperature(100e9)
    assert final_temperature == 2800
    assert cryostream_base.run_mode == RunModes.RUN.value
    assert cryostream_base.phase_id == PhaseIds.HOLD.value


@pytest.mark.asyncio
async def test_cool():
    cryostream_base = CryostreamBase()
    cryostream_base.ramp = Mock(cryostream_base.ramp)
    starting_temperature = cryostream_base.gas_temp
    target_temperature = starting_temperature - 50 * cK
    await cryostream_base.cool(target_temperature)
    assert cryostream_base.run_mode == RunModes.RUN.value
    assert cryostream_base.phase_id == PhaseIds.COOL.value
    cryostream_base.ramp.assert_awaited_once_with(
        cryostream_base.default_ramp_rate, target_temperature
    )


@pytest.mark.parametrize(
    "test_params",
    [
        pytest.param(
            {
                "initial_gas_temp": CryostreamBase.default_temp_shutdown,
                "expected_run_mode": RunModes.SHUTDOWNOK.value,
                "expected_gas_flow": {0},
            },
            id="shutdown okay",
        ),
        pytest.param(
            {
                "initial_gas_temp": CryostreamBase.default_temp_shutdown - 100 * cK,
                "expected_run_mode": RunModes.SHUTDOWNFAIL.value,
                "expected_gas_flow": {5, 10},
            },
            id="shutdown fails",
        ),
    ],
)
@pytest.mark.asyncio
async def test_end(test_params: Dict[str, Any]):
    def set_gas_flow(value: int, target_temp: int) -> None:
        if rand_bool():
            cryostream_base.gas_flow = 10
        else:
            cryostream_base.gas_flow = 5

    cryostream_base = CryostreamBase()
    cryostream_base.gas_temp = test_params["initial_gas_temp"]
    cryostream_base.ramp = Mock(cryostream_base.ramp, side_effect=set_gas_flow)
    await cryostream_base.end(ramp_rate=cryostream_base.max_rate)
    assert cryostream_base.phase_id == PhaseIds.END.value
    assert cryostream_base.run_mode == test_params["expected_run_mode"]
    assert cryostream_base.gas_flow in test_params["expected_gas_flow"]


@pytest.mark.parametrize(
    "test_params",
    [
        pytest.param(
            {
                "initial_gas_temp": CryostreamBase.default_temp_shutdown,
                "expected_run_mode": RunModes.SHUTDOWNOK.value,
            },
            id="shutdown okay",
        ),
        pytest.param(
            {
                "initial_gas_temp": CryostreamBase.default_temp_shutdown - 100 * cK,
                "expected_run_mode": RunModes.SHUTDOWNFAIL.value,
            },
            id="shutdown fails",
        ),
    ],
)
@pytest.mark.asyncio
async def test_purge(test_params: Dict[str, Any]):
    cryostream_base = CryostreamBase()
    cryostream_base.gas_temp = test_params["initial_gas_temp"]
    cryostream_base.ramp = Mock(cryostream_base.ramp)
    await cryostream_base.purge()
    assert cryostream_base.phase_id == PhaseIds.PURGE.value
    assert cryostream_base.run_mode == test_params["expected_run_mode"]


@pytest.mark.asyncio
async def test_stop():
    cryostream_base = CryostreamBase()
    await cryostream_base.stop()
    assert cryostream_base.gas_flow == 0
    assert cryostream_base._target_temp == cryostream_base.gas_temp
    assert cryostream_base.run_mode == RunModes.SHUTDOWNOK.value


@pytest.mark.parametrize(
    "test_params",
    argvalues=[
        {"temp": 350, "expected_gas_flow": 5},
        {"temp": 300, "expected_gas_flow": 10},
    ],
)
@pytest.mark.asyncio
async def test_turbo(test_params):
    cryostream_base = CryostreamBase()
    cryostream_base.gas_temp = test_params["temp"] * cK
    await cryostream_base.turbo(1)
    assert cryostream_base.turbo_mode == 1
    assert int(cryostream_base.gas_flow) == test_params["expected_gas_flow"]


def test_update_temperature():
    cryostream_base = CryostreamBase()
    cryostream_base._target_temp = cryostream_base.gas_temp - cryostream_base.gas_flow

    cryostream_base.update_temperature(1e9)
    assert cryostream_base.gas_temp == cryostream_base._target_temp


@pytest.mark.asyncio
async def test_set_status_format():
    cryostream_base = CryostreamBase()
    await cryostream_base.set_status_format(0)
    assert isinstance(cryostream_base.status, Status)

    await cryostream_base.set_status_format(1)
    assert isinstance(cryostream_base.extended_status, ExtendedStatus)


@pytest.mark.asyncio
async def test_get_status():
    cryostream_base = CryostreamBase()
    status = await cryostream_base.get_status(0)
    assert isinstance(status, Status)

    extended_status = await cryostream_base.get_status(1)
    assert isinstance(extended_status, ExtendedStatus)
