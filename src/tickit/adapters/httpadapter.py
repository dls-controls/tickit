import asyncio
import logging
from dataclasses import dataclass
from inspect import getmembers
from typing import Awaitable, Callable, Iterable, Optional, Tuple

from aiohttp import web
from aiohttp.web_routedef import RouteDef

from tickit.adapters.interpreters.endpoints.http_endpoint import HttpEndpoint
from tickit.core.adapter import RaiseInterrupt, AdapterIo
from tickit.core.device import Device

LOGGER = logging.getLogger(__name__)


class HttpAdapter:
    def get_endpoints(self) -> Iterable[Tuple[HttpEndpoint, Callable]]:
        """Returns list of endpoints.

        Fetches the defined HTTP endpoints in the device adapter, parses them and
        then yields them.

        Returns:
            Iterable[HttpEndpoint]: The list of defined endpoints

        Yields:
            Iterator[Iterable[HttpEndpoint]]: The iterator of the defined endpoints
        """
        for _, func in getmembers(self):
            endpoint = getattr(func, "__endpoint__", None)  # type: ignore
            if endpoint is not None and isinstance(endpoint, HttpEndpoint):
                yield endpoint, func

    def after_update(self) -> None:
        ...


class HttpIo(AdapterIo[HttpAdapter]):
    host: str
    port: int

    _stopped: Optional[asyncio.Event] = None
    _ready: Optional[asyncio.Event] = None

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
    ) -> None:
        self.host = host
        self.port = port
        self._stopped = None
        self._ready = None

    async def setup(
        self, adapter: HttpAdapter, raise_interrupt: RaiseInterrupt
    ) -> None:
        self._ensure_stopped_event().clear()
        endpoints = adapter.get_endpoints()
        await self._start_server(endpoints, raise_interrupt)
        self._ensure_ready_event().set()
        try:
            await self._ensure_stopped_event().wait()
        except asyncio.CancelledError:
            await self.stop()

    async def wait_until_ready(self, timeout: float = 1.0) -> None:
        while self._ready is None:
            await asyncio.sleep(0.1)
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    async def stop(self) -> None:
        stopped = self._ensure_stopped_event()
        if not stopped.is_set():
            await self.site.stop()
            await self.app.shutdown()
            await self.app.cleanup()
            self._ensure_stopped_event().set()
        if self._ready is not None:
            self._ready.clear()

    def _ensure_stopped_event(self) -> asyncio.Event:
        if self._stopped is None:
            self._stopped = asyncio.Event()
        return self._stopped

    def _ensure_ready_event(self) -> asyncio.Event:
        if self._ready is None:
            self._ready = asyncio.Event()
        return self._ready

    async def _start_server(
        self,
        endpoints: Iterable[Tuple[HttpEndpoint, Callable]],
        raise_interrupt: RaiseInterrupt,
    ):
        LOGGER.debug(f"Starting HTTP server... {self}")
        self.app = web.Application()
        definitions = self.create_route_definitions(endpoints, raise_interrupt)
        self.app.add_routes(list(definitions))
        runner = web.AppRunner(self.app)
        await runner.setup()
        self.site = web.TCPSite(runner, host=self.host, port=self.port)
        await self.site.start()

    def create_route_definitions(
        self,
        endpoints: Iterable[Tuple[HttpEndpoint, Callable]],
        raise_interrupt: RaiseInterrupt,
    ) -> Iterable[RouteDef]:
        for endpoint, func in endpoints:
            if endpoint.interrupt:
                func = _with_posthoc_task(func, raise_interrupt)
            yield endpoint.define(func)


def _with_posthoc_task(
    func: Callable[[web.Request], Awaitable[web.Response]],
    afterwards: Callable[[], Awaitable[None]],
) -> Callable[[web.Request], Awaitable[web.Response]]:
    # @functools.wraps
    async def wrapped(request: web.Request) -> web.Response:
        response = await func(request)
        await afterwards()
        return response

    return wrapped
