import asyncio
import logging

import aiozmq
import pytest
from mock import Mock
from mock.mock import AsyncMock, create_autospec

from tickit.adapters.zmqadapter import ZeroMQAdapter
from tickit.core.device import Device


@pytest.fixture
def mock_device() -> Device:
    return create_autospec(Device)


@pytest.fixture
def mock_raise_interrupt():
    async def raise_interrupt():
        return False

    return Mock(raise_interrupt)


@pytest.fixture
@pytest.mark.asyncio
async def mock_process_message_queue() -> AsyncMock:
    async def _process_message_queue():
        return True

    return AsyncMock(_process_message_queue)


@pytest.fixture
def zeromq_adapter() -> ZeroMQAdapter:
    zmq_adapter = ZeroMQAdapter()
    zmq_adapter._socket = AsyncMock()
    zmq_adapter._message_queue = Mock(asyncio.Queue)
    return zmq_adapter


def test_zeromq_adapter_constructor():
    ZeroMQAdapter()


@pytest.mark.asyncio
async def test_zeromq_adapter_start_stream(zeromq_adapter):
    await zeromq_adapter.start_stream()

    assert isinstance(zeromq_adapter._socket, aiozmq.stream.ZmqStream)

    await zeromq_adapter.close_stream()


@pytest.mark.asyncio
async def test_zeromq_adapter_close_stream(zeromq_adapter):
    await zeromq_adapter.start_stream()

    await zeromq_adapter.close_stream()
    await asyncio.sleep(0.1)

    assert None is zeromq_adapter._socket._transport


@pytest.mark.asyncio
async def test_zeromq_adapter_after_update(zeromq_adapter):

    zeromq_adapter.after_update()


@pytest.mark.asyncio
async def test_zeromq_adapter_send_message(zeromq_adapter):

    mock_message = AsyncMock()

    zeromq_adapter.send_message(mock_message)
    task = asyncio.current_task()
    asyncio.gather(task)
    zeromq_adapter._message_queue.put_nowait.assert_called_once()


@pytest.mark.asyncio
async def test_zeromq_adapter_run_forever_method(
    zeromq_adapter,
    mock_device: Device,
    mock_process_message_queue: AsyncMock,
    mock_raise_interrupt: Mock,
):

    zeromq_adapter._process_message_queue = mock_process_message_queue

    await zeromq_adapter.run_forever(mock_device, mock_raise_interrupt)

    zeromq_adapter._process_message_queue.assert_called_once()


@pytest.mark.asyncio
async def test_zeromq_adapter_check_if_running(zeromq_adapter):

    assert zeromq_adapter.check_if_running() is False


@pytest.mark.asyncio
async def test_zeromq_adapter_process_message_queue(zeromq_adapter):

    zeromq_adapter._process_message = AsyncMock()
    zeromq_adapter.check_if_running = Mock(return_value=False)

    await zeromq_adapter._process_message_queue()

    zeromq_adapter._process_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_zeromq_adapter_process_message(zeromq_adapter):

    mock_message = [b"test"]

    await zeromq_adapter._process_message(mock_message)

    zeromq_adapter._socket.write.assert_called_once()


@pytest.mark.asyncio
async def test_zeromq_adapter_process_message_no_message(zeromq_adapter, caplog):

    mock_message = None

    zeromq_adapter._socket.read.return_value = ("Data", None)

    with caplog.at_level(logging.DEBUG):
        await zeromq_adapter._process_message(mock_message)

    assert len(caplog.records) == 1
