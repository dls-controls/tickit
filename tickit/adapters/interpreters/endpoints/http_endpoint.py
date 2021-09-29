from dataclasses import dataclass
from typing import AnyStr, Awaitable, Callable, Generic

from aiohttp import web
from aiohttp.web_response import StreamResponse
from aiohttp.web_routedef import RouteDef


@dataclass(frozen=True)
class HTTPEndpoint(Generic[AnyStr]):
    """A decorator to register a device adapter method as a HTTP Endpoint.

    Args:
        url (str): The URL that will point to a specific endpoint.
        method (str): The method to use when using this endpoint.
        name (str): The name of the route.
        include_json (bool): A flag to indicate whether the route should include json.
        interrupt (bool): A flag indicating whether calling of the method should
            raise an adapter interrupt. Defaults to False.

    Returns:
        Callable:
            A decorator which registers the adapter method as an endpoint.
    """

    url: str
    method: str
    include_json: bool = False
    interrupt: bool = False

    def __call__(
        self, func: Callable[[web.Request], web.Response]
    ) -> Callable[[web.Request], web.Response]:
        """A decorator which registers the adapter method as an endpoint.

        Args:
            func (Callable): The adapter method to be registered as an endpoint.

        Returns:
            Callable: The registered adapter endpoint.
        """
        setattr(func, "__endpoint__", self)
        return func

    def define(
        self, func: Callable[[web.Request], Awaitable[StreamResponse]]
    ) -> RouteDef:
        """Performs the construction of the endpoint RouteDef for the HTTP Server.

        A method which performs the construction of the route definition of the method,
         URL and handler function for the endpoint, to then return to the HTTP Server.

        Args:
            func (Callable): The handler funcion to be attached to the route
            definition for the endpoint.

        Returns:
            RouteDef: The route definition for the endpoint.
        """
        return RouteDef(self.method, self.url, func, {})

    @classmethod
    def get(
        cls, url: str, include_json: bool = False, interrupt: bool = False
    ) -> "HTTPEndpoint":
        return cls(url, "GET", include_json, interrupt)