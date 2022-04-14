import asyncio
import logging
import traceback
import pjrpc
import pprint
from pjrpc.common import Request
from typing import Any, Callable

# type aliases for mypy's static analysis
RpcHandler = Callable[[Request, Any], Any]
Middleware = Callable[[Request, RpcHandler, Any], Any]


class ServerExceptionError(pjrpc.exc.JsonRpcError):
    code = 65500
    message = "Exception in the connection manager RPC server"


def serialize_requests() -> Middleware:
    """Return a middleware as closure which serializes handling RPC methods"""
    lock = asyncio.Lock()

    async def mw(request: Request, context: Any, handler: RpcHandler) -> Any:
        """PJRPC Middleware which serializes the execution of RPC methods"""
        async with lock:
            return await handler(request, context)

    return mw


def log_requests(logger: logging.Logger) -> Middleware:
    """Return a middleware as closure which using the given logger"""

    async def mw(request: Request, context: Any, handler: RpcHandler) -> Any:
        """PJRPC Middleware which logs the execution of called RPC methods"""
        if request.method in ["get_methods", "shutdown", "schedule_shutdown"]:
            return await handler(request, context)
        if request.is_notification:
            logger.info(f"got notification {request.method}")
            return await handler(request, context)
        logger.info(f"{request.method}({request.params})")
        result = await handler(request, context)
        logger.info(pprint.pformat(result))
        return result

    return mw


def stop_on_exception(logger: logging.Logger) -> Middleware:
    """Return a middleware as closure which using the given logger"""

    async def mw(request: Request, context: Any, handler: RpcHandler) -> Any:
        """Stop the server if handling a request raises an exception"""
        try:
            return await handler(request, context)
        except Exception as e:
            # Hint: For debugging, please remove or replace for production use:
            print(e)
            print(type(e))
            traceback.print_tb(e.__traceback__)
            running_async_event_loop = asyncio.get_event_loop()
            running_async_event_loop.call_soon(running_async_event_loop.stop)
            return ServerExceptionError()

    return mw


if __name__ == "__main__":
    from server_hello import run_aio_pika_example_server

    run_aio_pika_example_server("Hello from server_middleware.py!")