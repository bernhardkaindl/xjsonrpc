import asyncio
import functools as ft
import json
import itertools as it
import logging
from typing import Any, Callable, Dict, ItemsView, KeysView, List, Optional, Type, Iterator, Iterable, Union, ValuesView
from typing import cast, TypeVar

import xjsonrpc
from xjsonrpc.common import v20, BatchRequest, BatchResponse, Request, Response, UNSET, UnsetType
from xjsonrpc.server import utils
from . import validators

logger = logging.getLogger(__package__)

default_validator = validators.base.BaseValidator()
lst = List[Any]
dct = Dict[Any, Any]
RpcMethod = Callable[..., Any]
RpcParams = Optional[Union[lst, dct]]
Context = Optional[Any]


class Method:
    """
    JSON-RPC method wrapper. Stores method itself and some metainformation.

    :param method: method
    :param name: method name
    :param context: context name
    """

    def __init__(
        self,
        method: RpcMethod,
        name: Optional[str] = None,
        context: Optional[Any] = None,
    ):
        self.method = method
        self.name = name or method.__name__
        self.context = context

        meta = utils.set_meta(method, method_name=self.name, context_name=context)

        self.validator, self.validator_args = meta.get('validator', default_validator), meta.get('validator_args', {})

    def bind(self, params: RpcParams, context: Context = None,) -> RpcMethod:
        method_params = self.validator.validate_method(
            self.method, params, exclude=(self.context,) if self.context else (), **self.validator_args
        )

        if self.context is not None:
            method_params[self.context] = context

        return ft.partial(self.method, **method_params)

    def copy(self, **kwargs: Any) -> "Method":
        # sourcery skip: dict-assign-update-to-union
        cls_kwargs = dict(name=self.name, context=self.context)
        cls_kwargs.update(kwargs)

        return Method(method=self.method, **cls_kwargs)

    def __eq__(self, other: Any) -> bool:
        # sourcery skip: assign-if-exp, reintroduce-else, swap-if-expression
        if not isinstance(other, Method):
            return False

        return (self.method, self.name, self.context) == (other.method, other.name, other.context)


class ViewMethod(Method):
    """
    View method.

    :param view_cls: view class
    :param name: view class method name
    :param context: context name
    """

    def __init__(
        self,
        view_cls: Type['ViewMixin'],
        method_name: str,
        name: Optional[str] = None,
        context: Optional[Any] = None,
    ):
        super().__init__(getattr(view_cls, method_name), name or method_name, context)

        self.view_cls = view_cls
        self.method_name = method_name

    def bind(self, params: RpcParams, context: Optional[Any] = None) -> RpcMethod:
        view = self.view_cls(context) if self.context else self.view_cls()  # type: ignore
        method = getattr(view, self.method_name)

        method_params = self.validator.validate_method(method, params, **self.validator_args)

        return ft.partial(method, **method_params)

    def copy(self, **kwargs: Any) -> 'ViewMethod':
        # sourcery skip: dict-assign-update-to-union
        cls_kwargs = dict(name=self.name, context=self.context)
        cls_kwargs.update(kwargs)

        return ViewMethod(view_cls=self.view_cls, method_name=self.method_name, **cls_kwargs)


class ViewMixin:
    """
    Simple class based method handler mixin. Exposes all public methods.
    """

    @classmethod
    def __methods__(cls) -> Any:
        for attr_name in filter(lambda name: not name.startswith('_'), dir(cls)):
            attr = getattr(cls, attr_name)
            if callable(attr):
                yield attr


class MethodRegistry:
    """
    Method registry.

    :param prefix: method name prefix to be used for naming containing methods
    """

    def __init__(self, prefix: Optional[str] = None):
        self._prefix = prefix
        self._registry: Dict[str, Method] = {}

    def __iter__(self) -> Iterator[str]:
        """
        Returns registry method iterator.
        """

        return iter(self._registry)

    def __getitem__(self, item: str) -> Method:
        """
        Returns a method from the registry by name.

        :param item: method name
        :returns: found method
        :raises: KeyError
        """

        return self._registry[item]

    def items(self) -> ItemsView[str, Method]:
        return self._registry.items()

    def keys(self) -> KeysView[str]:
        return self._registry.keys()

    def values(self) -> ValuesView[Method]:
        return self._registry.values()

    def get(self, item: str) -> Optional[Method]:
        """
        Returns a method from the registry by name.

        :param item: method name
        :returns: found method or `None`
        """

        return self._registry.get(item)

    def add(
        self,
        rpc_method: RpcMethod,
        name: Optional[str] = None,
        context: Context = None,
    ) -> RpcMethod:
        """
        Decorator adding decorated method to the registry.
        :param rpc_method: method
        :param name: method name to be used instead of `__name__` attribute
        :param context: parameter name to be used as an application context
        :returns: decorated method or decorator
        """
        # https://stackoverflow.com/questions/65588913/mypy-type-annotations-for-a-decorator
        t = TypeVar("t", bound=Callable[..., Any])

        def decorator(method: t) -> t:
            full_name = ".".join(filter(None, (self._prefix, name or method.__name__)))
            self.add_methods(Method(method, full_name, context))
            return method

        return decorator(rpc_method)

    def add_methods(self, *methods: Union[RpcMethod, Method]) -> None:
        """
        Adds methods to the registry.

        :param methods: methods to be added. Each one can be an instance of :py:class:`xjsonrpc.server.Method`
                        or plain method
        """

        for method in methods:
            if isinstance(method, Method):
                self._add_method(method)
            else:
                self.add(method)

    def view(
        self, maybe_view: Optional[Type[ViewMixin]] = None, context: Optional[Any] = None, prefix: Optional[str] = None,
    ) -> Union[ViewMixin, Callable[..., Any]]:
        """
        Methods view decorator.

        :param maybe_view: view class instance or `None`
        :param context: application context name
        :param prefix: view methods prefix
        :return: decorator or decorated view
        """

        def decorator(view: Type[ViewMixin]) -> Type[ViewMixin]:
            for method in view.__methods__():
                full_name = '.'.join(filter(None, (self._prefix, prefix, method.__name__)))
                self._add_method(ViewMethod(view, method.__name__, full_name, context))

            return view

        # maybe_view's type depends on the usage of the decorator.  It's a View
        # if it's used as `@view` but ``None`` if used as `@view()`.
        if maybe_view is None:
            return decorator
        else:
            return decorator(maybe_view)

    def merge(self, other: 'MethodRegistry') -> None:
        """
        Merges two registries.

        :param other: registry to be merged in the current one
        """

        for name, method in other.items():
            if self._prefix:
                name = f'{self._prefix}.{name}'

            self._add_method(method.copy(name=name))

    def _add_method(self, method: Method) -> None:
        if method.name in self._registry:
            logger.warning(f"method '{method.name}' already registered")

        self._registry[method.name] = method


class JSONEncoder(xjsonrpc.JSONEncoder):
    """
    Server JSON encoder. All custom server encoders should be inherited from it.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, validators.base.ValidationError):
            return list(o.args)

        return super().default(o)


class BaseDispatcher:
    """
    Method dispatcher.

    :param request_class: JSON-RPC request class
    :param response_class: JSON-RPC response class
    :param batch_request: JSON-RPC batch request class
    :param batch_response: JSON-RPC batch response class
    :param json_loader: request json loader
    :param json_dumper: response json dumper
    :param json_encoder: response json encoder
    :param json_decoder: request json decoder
    :param middlewares: request middlewares
    :param error_handlers: request error handlers
    """

    def __init__(
        self,
        *,
        request_class: Type[Request] = v20.Request,
        response_class: Type[Response] = v20.Response,
        batch_request: Type[BatchRequest] = v20.BatchRequest,
        batch_response: Type[BatchResponse] = v20.BatchResponse,
        json_loader: Callable[..., Any] = json.loads,
        json_dumper: Callable[..., str] = json.dumps,
        json_encoder: Type[JSONEncoder] = JSONEncoder,
        json_decoder: Optional[Type[json.JSONDecoder]] = None,
        middlewares: Iterable[Callable[..., Any]] = (),
        error_handlers: Dict[Union[None, int, Exception], List[Callable[..., Any]]] = {},
    ):
        self._json_loader = json_loader
        self._json_dumper = json_dumper
        self._json_encoder = json_encoder
        self._json_decoder = json_decoder
        self._request_class = request_class
        self._response_class = response_class
        self._batch_request = batch_request
        self._batch_response = batch_response
        self._middlewares = list(middlewares)
        self._error_handlers = error_handlers

        self._registry = MethodRegistry()

    @property
    def registry(self) -> MethodRegistry:
        return self._registry

    def add(
        self,
        method: RpcMethod,
        name: Optional[str] = None,
        context: Optional[Any] = None,
    ) -> None:
        """
        Adds method to the registry.

        :param method: method
        :param name: method name
        :param context: application context name
        """

        self._registry.add(method, name, context)

    def add_methods(self, *methods: Union[MethodRegistry, Method, RpcMethod]) -> None:
        """
        Adds methods to the registry.

        :param methods: method list. Each method may be an instance of :py:class:`xjsonrpc.server.MethodRegistry`,
                        :py:class:`xjsonrpc.server.Method` or plain function
        """

        for method in methods:
            if isinstance(method, MethodRegistry):
                self._registry.merge(method)
            elif isinstance(method, Method):
                self._registry.add_methods(method)
            else:
                self._registry.add(method)

    def view(self, view: Type[ViewMixin]) -> None:
        """
        Adds class based view to the registry.

        :param view: view to be added
        """

        self._registry.view(view)


class Dispatcher(BaseDispatcher):
    def dispatch(self, request_text: str, context: Optional[Any] = None) -> Optional[str]:
        """
        Deserializes request, dispatches it to the required method and serializes the result.

        :param request_text: request text representation
        :param context: application context (if supported)
        :return: response text representation
        """
        logger.getChild('request').debug("request received: %s", request_text)
        response: Union[Response, BatchResponse, UnsetType] = UNSET
        try:
            request_json = self._json_loader(request_text, cls=self._json_decoder)
            if isinstance(request_json, (list, tuple)):
                batch_request = self._batch_request.from_json(request_json)
                response = self._batch_response(
                    *cast(
                        BatchResponse,
                        filter(
                            lambda resp: resp is not UNSET, (
                                self._handle_request(request, context)
                                for request in batch_request
                            )
                        )
                    )
                )
            else:
                request = self._request_class.from_json(request_json)
                response = self._handle_request(request, context)

        except json.JSONDecodeError as e:
            response = self._response_class(id=None, error=xjsonrpc.exceptions.ParseError(data=str(e)))

        except (xjsonrpc.exceptions.DeserializationError, xjsonrpc.exceptions.IdentityError) as e:
            response = self._response_class(id=None, error=xjsonrpc.exceptions.InvalidRequestError(data=str(e)))

        if isinstance(response, UnsetType):
            return None
        response_text = self._json_dumper(response.to_json(),
                                          cls=self._json_encoder)
        logger.getChild('response').debug("response sent: %s", response_text)
        return response_text

    def _handle_request(self, request: Request, context: Optional[Any]) -> Union[UnsetType, Response]:
        try:
            handler = self._handle_rpc_request

            for middleware in reversed(self._middlewares):
                handler = ft.partial(middleware, handler=handler)

            return handler(request, context)

        except xjsonrpc.exceptions.JsonRpcError as e:
            logger.info("method execution error %s(%r): %r", request.method, request.params, e)
            error = e

        except Exception as e:
            logger.exception("internal server error: %r", e)
            error = xjsonrpc.exceptions.InternalError()

        for handler in it.chain(self._error_handlers.get(None, []), self._error_handlers.get(error.code, [])):
            error = handler(request, context, error)

        if request.id is None:
            return UNSET

        return self._response_class(id=request.id, error=error)

    def _handle_rpc_request(self, request: Request, context: Optional[Any]) -> Union[UnsetType, Response]:
        result = self._handle_rpc_method(request.method, request.params, context)
        if request.id is None:
            return UNSET

        return self._response_class(id=request.id, result=result)

    def _handle_rpc_method(
        self, method_name: str, params: Optional[Union[lst, dct]], context: Optional[Any]
    ) -> Any:
        method = self._registry.get(method_name)
        if method is None:
            raise xjsonrpc.exceptions.MethodNotFoundError(data=f"method '{method_name}' not found")

        try:
            bound = method.bind(params, context=context)
        except validators.ValidationError as e:
            raise xjsonrpc.exceptions.InvalidParamsError(data=e) from e

        try:
            return bound()

        except xjsonrpc.exceptions.JsonRpcError:
            raise

        except Exception as e:
            logger.exception("method unhandled exception %s(%r): %r", method_name, params, e)
            raise xjsonrpc.exceptions.ServerError() from e


class AsyncDispatcher(BaseDispatcher):
    """
    Asynchronous method dispatcher.
    """

    async def dispatch(self, request_text: str, context: Optional[Any] = None) -> Optional[str]:
        """
        Deserializes request, dispatches it to the required method and serializes the result.

        :param request_text: request text representation
        :param context: application context (if supported)
        :return: response text representation
        """
        logger.getChild('request').debug("request received: %s", request_text)
        response: Union[Response, BatchResponse, UnsetType] = UNSET
        try:
            request_json = self._json_loader(request_text, cls=self._json_decoder)
            if isinstance(request_json, (list, tuple)):
                batch_request = self._batch_request.from_json(request_json)
                response = self._batch_response(
                    *filter(
                        lambda resp: resp is not UNSET, await asyncio.gather(
                            *(self._handle_request(request, context)
                              for request in batch_request)
                        ),
                    )
                )
            else:
                request = self._request_class.from_json(request_json)
                response = await self._handle_request(request, context)
                if not response or isinstance(response, UnsetType):
                    return None
                response_text = self._json_dumper(response.to_json(),
                                                  cls=self._json_encoder)
        except json.JSONDecodeError as e:
            response = self._response_class(
                id=None, error=xjsonrpc.exceptions.ParseError(data=str(e))
            )
        except (xjsonrpc.exceptions.DeserializationError,
                xjsonrpc.exceptions.IdentityError) as e:
            response = self._response_class(id=None, error=xjsonrpc.exceptions.InvalidRequestError(data=str(e)))

        if isinstance(response, UnsetType):
            return None
        response_text = self._json_dumper(response.to_json(),
                                          cls=self._json_encoder)
        logger.getChild('response').debug("response sent: %s", response_text)
        return response_text

    async def _handle_request(self, request: Request, context: Optional[Any]) -> Union[UnsetType, Response]:
        try:
            handler = self._handle_rpc_request

            for middleware in reversed(self._middlewares):
                handler = ft.partial(middleware, handler=handler)

            return await handler(request, context)

        except xjsonrpc.exceptions.JsonRpcError as e:
            logger.info("method execution error %s(%r): %r", request.method, request.params, e)
            error = e

        except Exception as e:
            logger.exception("internal server error: %r", e)
            error = xjsonrpc.exceptions.InternalError()

        for handler in it.chain(self._error_handlers.get(None, []), self._error_handlers.get(error.code, [])):
            error = await handler(request, context, error)

        if request.id is None:
            return UNSET

        return self._response_class(id=request.id, error=error)

    async def _handle_rpc_request(self, request: Request, context: Optional[Any]) -> Union[UnsetType, Response]:
        result = await self._handle_rpc_method(request.method, request.params, context)
        if request.id is None:
            return UNSET

        return self._response_class(id=request.id, result=result)

    async def _handle_rpc_method(
        self, method_name: str, params: RpcParams, context: Optional[Any],
    ) -> Any:
        method = self._registry.get(method_name)
        if method is None:
            raise xjsonrpc.exceptions.MethodNotFoundError(data=f"method '{method_name}' not found")

        try:
            bound = method.bind(params, context=context)
        except validators.ValidationError as e:
            raise xjsonrpc.exceptions.InvalidParamsError(data=e) from e

        try:
            result = bound()
            if asyncio.iscoroutine(result):
                result = await result

            return result

        except xjsonrpc.exceptions.JsonRpcError:
            raise

        except Exception as e:
            logger.exception("method unhandled exception %s(%r): %r", method_name, params, e)
            raise xjsonrpc.exceptions.ServerError() from e
