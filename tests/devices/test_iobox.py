from typing import Any

import pytest

from tickit.core.typedefs import SimTime
from tickit.devices.iobox import IoBoxDevice


@pytest.fixture
def box() -> IoBoxDevice[int, Any]:
    return IoBoxDevice()


def test_raises_error_if_no_values(box: IoBoxDevice[int, Any]) -> None:
    with pytest.raises(KeyError):
        box.read(4)


def test_writes_pending_until_update(box: IoBoxDevice[int, Any]):
    box.write(4, "foo")
    box.update(SimTime(0), {})
    assert "foo" == box.read(4)
    box.write(4, "bar")
    assert "foo" == box.read(4)
    box.update(SimTime(0), {})
    assert "bar" == box.read(4)
