import logging

from aiohttp import web
from apischema import serialize

from tickit.adapters.httpadapter import HTTPAdapter
from tickit.adapters.interpreters.endpoints.http_endpoint import HTTPEndpoint
from tickit.adapters.zmqadapter import ZeroMQAdapter
from tickit.devices.eiger.eiger import EigerDevice
from tickit.devices.eiger.eiger_schema import SequenceComplete, Value, construct_value
from tickit.devices.eiger.eiger_status import State
from tickit.devices.eiger.filewriter.eiger_filewriter import EigerFileWriterAdapter
from tickit.devices.eiger.monitor.eiger_monitor import EigerMonitorAdapter
from tickit.devices.eiger.stream.eiger_stream import EigerStreamAdapter

DETECTOR_API = "detector/api/1.8.0"

LOGGER = logging.getLogger("EigerAdapter")


class EigerRESTAdapter(
    HTTPAdapter, EigerStreamAdapter, EigerMonitorAdapter, EigerFileWriterAdapter
):
    """An Eiger adapter which parses the commands sent to the HTTP server."""

    device: EigerDevice

    @HTTPEndpoint.get(f"/{DETECTOR_API}" + "/config/{parameter_name}")
    async def get_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting configuration variables from the Eiger.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["parameter_name"]

        if hasattr(self.device.settings, param):

            data = construct_value(self.device.settings, param)

        else:
            data = serialize(Value("None", "string", access_mode="None"))

        return web.json_response(data)

    @HTTPEndpoint.put(
        f"/{DETECTOR_API}" + "/config/{parameter_name}", include_json=True
    )
    async def put_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting configuration variables for the Eiger.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["parameter_name"]

        response = await request.json()

        if self.device.get_state()["value"] != State.IDLE.value:
            LOGGER.warning("Eiger not initialized or is currently running.")
            return web.json_response(serialize([]))
        elif (
            hasattr(self.device.settings, param)
            and self.device.get_state()["value"] == State.IDLE.value
        ):
            attr = response["value"]

            LOGGER.debug(f"Changing to {str(attr)} for {str(param)}")

            self.device.settings[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(serialize([]))

    @HTTPEndpoint.get(f"/{DETECTOR_API}" + "/status/{status_param}")
    async def get_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["status_param"]

        if hasattr(self.device.status, param):

            data = construct_value(self.device.status, param)

        else:
            data = serialize(Value("None", "string", access_mode="None"))

        return web.json_response(data)

    @HTTPEndpoint.get(f"/{DETECTOR_API}" + "/status/board_000/{status_param}")
    async def get_board_000_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        return await self.get_status(request)

    @HTTPEndpoint.get(f"/{DETECTOR_API}" + "/status/builder/{status_param}")
    async def get_builder_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting the status of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        return await self.get_status(request)

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/initialize", interrupt=True)
    async def initialize_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'initialize' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.initialize()

        LOGGER.debug("Initializing Eiger...")
        return web.json_response(serialize(SequenceComplete(1)))

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/arm", interrupt=True)
    async def arm_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'arm' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.arm()

        LOGGER.debug("Arming Eiger...")
        return web.json_response(serialize(SequenceComplete(2)))

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/disarm", interrupt=True)
    async def disarm_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'disarm' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.disarm()

        LOGGER.debug("Disarming Eiger...")
        return web.json_response(serialize(SequenceComplete(3)))

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/trigger", interrupt=False)
    async def trigger_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'trigger' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        trigger_message = await self.device.trigger()

        LOGGER.debug(trigger_message)

        await self.raise_interrupt()
        await self.device.finished_aquisition.wait()

        return web.json_response(serialize(SequenceComplete(4)))

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/cancel", interrupt=True)
    async def cancel_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'cancel' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.cancel()

        LOGGER.debug("Cancelling Eiger...")
        return web.json_response(serialize(SequenceComplete(5)))

    @HTTPEndpoint.put(f"/{DETECTOR_API}" + "/command/abort", interrupt=True)
    async def abort_eiger(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for the 'abort' command of the Eiger.

        Args:
            request (web.Request): The request object that takes the request method.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        await self.device.abort()

        LOGGER.debug("Aborting Eiger...")
        return web.json_response(serialize(SequenceComplete(6)))


class EigerZMQAdapter(ZeroMQAdapter):
    """An Eiger adapter which parses the data to send along a ZeroMQStream."""

    device: EigerDevice

    def after_update(self) -> None:
        """Updates IOC values immediately following a device update."""
        for message in self.device.consume_data():
            self.send_message(message)
