import asyncio
import logging
from typing import Any, Awaitable, Callable

import aiozmq
import zmq

from examples.devices.counter import Counter
from tickit.core.adapter import ConfigurableAdapter

LOGGER = logging.getLogger(__name__)


class ZeroMQAdapter(ConfigurableAdapter):
    """An adapter for a ZeroMQ data stream."""

    _device: Counter
    _raise_interrupt: Callable[[], Awaitable[None]]

    _dealer: zmq.DEALER
    _router: zmq.ROUTER

    def __init__(
        self,
        device: Counter,
        raise_interrupt: Callable[[], Awaitable[None]],
        host: str = "127.0.0.1",
        port: int = 5555,
    ) -> None:
        """A ZeroMQAdapter constructor which instantiates a TcpServer with host and port.

        Args:
            device (ZMQStream): The ZMQ stream/device which this adapter is attached to
            raise_interrupt (Callable): A callback to request that the device is
                updated immediately.
            host (Optional[str]): The host address of the TcpServer. Defaults to
                "localhost".
            port (Optional[int]): The bound port of the TcpServer. Defaults to 5555.
        """
        self._device = device
        # self._raise_interrupt = raise_interrupt
        self._host = host
        self._port = port

    def after_update(self) -> None:
        """Updates IOC values immediately following a device update."""
        current_value = self._device.get_value()
        LOGGER.info(f"Value updated to : {current_value}")
        asyncio.create_task(self.send_message(current_value))

    async def start_stream(self) -> None:
        """[summary]."""
        LOGGER.debug("Starting stream...")
        self._router = await aiozmq.create_zmq_stream(
            zmq.ROUTER, bind=f"tcp://{self._host}:{self._port}"
        )

        addr = list(self._router.transport.bindings())[0]
        self._dealer = await aiozmq.create_zmq_stream(zmq.DEALER, connect=addr)

    async def close_stream(self) -> None:
        """[summary]."""
        self._dealer.close()
        self._router.close()

    async def send_message(self, reply: Any) -> None:
        if reply is None:
            LOGGER.debug("No reply...")
            pass
        else:
            LOGGER.debug("Data from ZMQ stream: {!r}".format(reply))

            msg = (b"Data", str(reply).encode("utf-8"))
            self._dealer.write(msg)
            data = await self._router.read()
            self._router.write(data)
            answer = await self._dealer.read()
            LOGGER.info("Received {!r}".format(answer))
            await asyncio.sleep(1.0)

    async def run_forever(self) -> None:
        """[summary].

        Yields:
            [type]: [description]
        """
        await self.start_stream()