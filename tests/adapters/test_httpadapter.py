from typing import Iterable

import pytest
from aiohttp import web
from mock import Mock
from mock.mock import create_autospec, patch

from tickit.adapters.httpadapter import HTTPAdapter
from tickit.adapters.interpreters.endpoints.http_endpoint import HTTPEndpoint
from tickit.core.device import Device


@pytest.fixture
def mock_device() -> Device:
    return create_autospec(Device)


@pytest.fixture
def mock_raise_interrupt():
    async def raise_interrupt():
        return False

    return Mock(raise_interrupt)


class MockAdapter(HTTPAdapter):

    device: Device

    @HTTPEndpoint.get("/mock_endpoint", interrupt=True)
    async def mock_endpoint(request: web.Request) -> web.Response:
        return web.Response(text="test")


@pytest.fixture
def http_adapter() -> HTTPAdapter:
    http_adapter = HTTPAdapter()
    return http_adapter


def test_http_adapter_constructor():
    HTTPAdapter()


@pytest.fixture
def patch_asyncio_event_wait() -> Iterable[Mock]:
    with patch(
        "tickit.core.components.device_simulation.asyncio.Event.wait", autospec=True
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_http_adapter_run_forever_method(
    http_adapter,
    mock_device: Device,
    mock_raise_interrupt: Mock,
    patch_asyncio_event_wait: Mock,
):
    await http_adapter.run_forever(mock_device, mock_raise_interrupt)

    patch_asyncio_event_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_http_adapter_endpoints(
    mock_device: Device, mock_raise_interrupt: Mock, patch_asyncio_event_wait: Mock
):

    adapter = MockAdapter(port=8081)
    await adapter.run_forever(mock_device, mock_raise_interrupt)

    resp = await list(adapter.endpoints())[0].handler()

    assert resp.text == "test"
