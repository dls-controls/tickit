import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable

import aiozmq
import zmq

from tickit.core.adapter import Adapter, RaiseInterrupt
from tickit.core.device import Device

LOGGER = logging.getLogger("ZmqAdapter")


@dataclass
class ZeroMQAdapter(Adapter):
    """An adapter for a ZeroMQ data stream."""

    zmq_host: str = "127.0.0.1"
    zmq_port: int = 5555
    running: bool = False

    async def start_stream(self) -> None:
        """Start the ZeroMQ stream."""
        LOGGER.debug("Starting stream...")

        self._socket = await aiozmq.create_zmq_stream(
            zmq.PUSH, bind=f"tcp://{self.zmq_host}:{self.zmq_port}"
        )
        LOGGER.debug(f"Stream started. {self._socket}")

    async def close_stream(self) -> None:
        """Close the ZeroMQ stream."""
        self._socket.close()

        self.running = False

    def send_message(self, message: bytes) -> None:
        """Send a message down the ZeroMQ stream.

        Sets up an asyncio task to put the message on the message queue, before
        being processed.

        Args:
            message (str): The message to send down the ZeroMQ stream.
        """
        self._message_queue.put_nowait(message)

    async def run_forever(
        self, device: Device, raise_interrupt: RaiseInterrupt
    ) -> None:
        """Runs the ZeroMQ adapter continuously."""
        await super().run_forever(device, raise_interrupt)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        await self.start_stream()
        self.running = True
        await self._process_message_queue()

    def check_if_running(self):
        """Returns the running state of the adapter."""
        return self.running

    async def _process_message_queue(self) -> None:
        running = True
        while running:
            message = await self._message_queue.get()
            await self._process_message(message)
            running = self.check_if_running()

    async def _process_message(self, message: Iterable[bytes]) -> None:
        if message is not None:

            self._socket.write(message)
        else:
            LOGGER.debug("No message")
