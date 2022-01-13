import asyncio
import logging
from dataclasses import dataclass
from inspect import getmembers
from typing import Callable, Iterable

from aiohttp import web
from aiohttp.web_routedef import RouteDef

from tickit.adapters.interpreters.endpoints.http_endpoint import HTTPEndpoint
from tickit.core.adapter import Adapter, RaiseInterrupt
from tickit.core.device import Device

LOGGER = logging.getLogger(__name__)


@dataclass
class HTTPAdapter(Adapter):
    """An adapter implementation which delegates to a server and sets up endpoints.

    An adapter implementation which delegates the hosting of an http requests to a
    server and sets up the endpoints for said server.
    """

    host: str = "localhost"
    port: int = 8080

    async def run_forever(
        self, device: Device, raise_interrupt: RaiseInterrupt
    ) -> None:
        """Runs the server continously."""
        await super().run_forever(device, raise_interrupt)

        await self._start_server()

        try:
            await asyncio.Event().wait()
        finally:
            # TODO: This doesn't work yet due to asyncio's own exception handler
            await self.app.shutdown()
            await self.app.cleanup()

    async def _start_server(self):
        LOGGER.debug(f"Starting HTTP server... {self}")
        self.app = web.Application()
        self.app.add_routes(list(self.endpoints()))
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()

    def endpoints(self) -> Iterable[RouteDef]:
        """Returns list of endpoints.

        Fetches the defined HTTP endpoints in the device adapter, parses them and
        then yields them.

        Returns:
            Iterable[HTTPEndpoint]: The list of defined endpoints

        Yields:
            Iterator[Iterable[HTTPEndpoint]]: The iterator of the defined endpoints
        """
        for _, func in getmembers(self):
            endpoint: HTTPEndpoint = getattr(func, "__endpoint__", None)
            if endpoint is not None:
                yield self._make_route_def(func, endpoint)

    def _make_route_def(self, func: Callable, endpoint: HTTPEndpoint) -> RouteDef:
        # Create wrapper around endpoint function that calls interrupt where necessary
        async def wrapped_func(*args, **kwargs):
            reply = await func(*args, **kwargs)
            if endpoint.interrupt:
                await self.raise_interrupt()
            return reply

        return endpoint.define(wrapped_func)
