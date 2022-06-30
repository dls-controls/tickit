from typing import Dict

import pytest
from mock import MagicMock, Mock, create_autospec, mock_open, patch

from tickit.adapters.epicsadapter import EpicsAdapter, InputRecord
from tickit.core.adapter import Adapter, Interpreter
from tickit.core.device import Device


@pytest.fixture
def MockDevice() -> Mock:
    return create_autospec(Device, instance=False)


@pytest.fixture
def MockInterpreter() -> Mock:
    return MagicMock(Interpreter, instance=True)


@pytest.fixture
def epics_adapter() -> EpicsAdapter:
    return EpicsAdapter("ioc_name")  # type: ignore


@pytest.fixture
def input_record() -> InputRecord:
    def setter():
        return None

    def getter():
        return False

    return InputRecord("input", Mock(setter), Mock(getter))


def test_epics_adapter_is_adapter():
    assert issubclass(EpicsAdapter, Adapter)


def test_epics_adapter_constuctor(epics_adapter: EpicsAdapter):
    pass


def test_epics_adapter_interrupt_records_empty_on_construct():
    with pytest.raises(AttributeError):
        EpicsAdapter.interrupt_records


def test_link_input_on_interrupt(
    epics_adapter: EpicsAdapter, input_record: InputRecord
):
    def getter():
        return False

    getter = Mock(getter)
    epics_adapter.interrupt_records = {}
    epics_adapter.link_input_on_interrupt(input_record, getter)
    assert epics_adapter.interrupt_records[input_record] == getter


def test_epics_adapter_after_update_method(
    epics_adapter: EpicsAdapter, input_record: InputRecord
):
    def getter():
        return False

    getter = Mock(getter)
    epics_adapter.interrupt_records = {}
    epics_adapter.interrupt_records[input_record] = getter

    epics_adapter.after_update()

    input_record.set.assert_called()


def record_db_file_contents() -> Dict[str, bytes]:
    return {
        "data": b"""record(ao, "$(device):GAIN") {
        field(DTYP, "Hy8001")
        field(OMSL, "supervisory")
        field(OUT, "#C1 S0 @")
        field(DESC, "Gain value")
        field(EGU, "A")
        }""",
        "expected": b"""record(ao, "$(device):GAIN") {
        field(OMSL, "supervisory")
        field(OUT, "#C1 S0 @")
        field(DESC, "Gain value")
        field(EGU, "A")
        }""",
    }


def filter1_db_file_contents() -> Dict[str, bytes]:
    return {
        "data": b"""record(bo, "$(device):FILTER") {
        field(DTYP, "$(DTYP)")
        field(SCAN, "Passive")
        field(ZNAM, "Out")
        field(ONAM, "In")
        field(VAL, "0")
        field(OMSL, "closed_loop")
        }""",
        "expected": b"""record(bo, "$(device):FILTER") {
        field(SCAN, "Passive")
        field(ZNAM, "Out")
        field(ONAM, "In")
        field(VAL, "0")
        field(OMSL, "closed_loop")
        }""",
    }


@pytest.mark.parametrize(
    "test_params",
    [
        pytest.param(record_db_file_contents(), id="record.db file contents"),
        pytest.param(filter1_db_file_contents(), id="filter.db file contents"),
    ],
)
def test_epics_adapter_load_records_without_DTYP_fields_method(
    epics_adapter: EpicsAdapter,
    test_params: Dict[str, bytes],
):

    data = test_params["data"]
    path = MagicMock()
    path.open = mock_open(read_data=data)
    with patch("os.unlink") as mock_unlink:
        epics_adapter.load_records(
            path, substitutions={"device": "test"}, remove_dtypes=True
        )
        unlink_args = mock_unlink.call_args.args

    out_filename = unlink_args[0]
    written_data = open(out_filename, "rb").read()
    assert str(written_data).strip() == str(test_params["expected"]).strip()
