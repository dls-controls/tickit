import logging

from aiohttp import web
from apischema import serialize
from typing_extensions import TypedDict

from tickit.adapters.interpreters.endpoints.http_endpoint import HTTPEndpoint
from tickit.core.typedefs import SimTime
from tickit.devices.eiger.eiger_schema import construct_value
from tickit.devices.eiger.filewriter.filewriter_config import FileWriterConfig
from tickit.devices.eiger.filewriter.filewriter_status import FileWriterStatus

LOGGER = logging.getLogger(__name__)

FILEWRITER_API = "filewriter/api/1.8.0"


class EigerFileWriter:
    """Simulation of an Eiger FileWriter."""

    #: An empty typed mapping of input values
    Inputs: TypedDict = TypedDict("Inputs", {})
    #: A typed mapping containing the 'value' output value
    Outputs: TypedDict = TypedDict("Outputs", {})

    def __init__(self) -> None:
        """An Eiger FileWriter constructor."""
        self.filewriter_status: FileWriterStatus = FileWriterStatus()
        self.filewriter_config: FileWriterConfig = FileWriterConfig()
        self.filewriter_callback_period = SimTime(int(1e9))


class EigerFileWriterAdapter:
    """An adapter for the FileWriter."""

    device: EigerFileWriter

    @HTTPEndpoint.get(f"/{FILEWRITER_API}" + "/config/{param}")
    async def get_filewriter_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting config values from the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.filewriter_config, param)

        return web.json_response(data)

    @HTTPEndpoint.put(f"/{FILEWRITER_API}" + "/config/{param}", include_json=True)
    async def put_filewriter_config(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for setting config values for the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter
            and value.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        response = await request.json()

        if hasattr(self.device.filewriter_config, param):
            attr = response["value"]

            LOGGER.debug(f"Changing to {attr} for {param}")

            self.device.filewriter_config[param] = attr

            LOGGER.debug("Set " + str(param) + " to " + str(attr))
            return web.json_response(serialize([param]))
        else:
            LOGGER.debug("Eiger has no config variable: " + str(param))
            return web.json_response(serialize([]))

    @HTTPEndpoint.get(f"/{FILEWRITER_API}" + "/status/{param}")
    async def get_filewriter_status(self, request: web.Request) -> web.Response:
        """A HTTP Endpoint for requesting status values from the Filewriter.

        Args:
            request (web.Request): The request object that takes the given parameter.

        Returns:
            web.Response: The response object returned given the result of the HTTP
                request.
        """
        param = request.match_info["param"]

        data = construct_value(self.device.filewriter_status, param)

        return web.json_response(data)
