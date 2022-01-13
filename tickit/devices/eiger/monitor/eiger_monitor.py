import logging

from aiohttp import web
from apischema import serialize
from typing_extensions import TypedDict

from tickit.adapters.interpreters.endpoints.http_endpoint import HTTPEndpoint
from tickit.core.typedefs import SimTime
from tickit.devices.eiger.eiger_schema import construct_value
from tickit.devices.eiger.monitor.monitor_config import MonitorConfig
from tickit.devices.eiger.monitor.monitor_status import MonitorStatus

LOGGER = logging.getLogger(__name__)

MONITOR_API = "monitor/api/1.8.0"


class EigerMonitor:
    """Simulation of an Eiger Monitor."""

    #: An empty typed mapping of input values
    Inputs: TypedDict = TypedDict("Inputs", {})
    #: A typed mapping containing the 'value' output value
    Outputs: TypedDict = TypedDict("Outputs", {})

    def __init__(self) -> None:
        """An Eiger Monitor constructor."""
        self.monitor_status: MonitorStatus = MonitorStatus()
        self.monitor_config: MonitorConfig = MonitorConfig()
        self.monitor_callback_period = SimTime(int(1e9))


class EigerMonitorAdapter:
    """An adapter for the Monitor."""

    device: EigerMonitor

    @HTTPEndpoint.get(f"/{MONITOR_API}" + "/config/{param}")
    async def get_monitor_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting config values from the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.monitor_config, param)

        return web.json_response(data)

    @HTTPEndpoint.put(f"/{MONITOR_API}" + "/config/{param}", include_json=True)
    async def put_monitor_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting config values for the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        response = await request.json()

        if hasattr(self.device.monitor_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.monitor_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(serialize([]))

    @HTTPEndpoint.get(f"/{MONITOR_API}" + "/status/{param}")
    async def get_monitor_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting status values from the Monitor.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.monitor_status, param)

        return web.json_response(data)
