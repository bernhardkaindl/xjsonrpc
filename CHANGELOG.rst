Changelog
=========

1.4.3 (2022-05-09)
------------------

- move message.ack() in aio_pika.Server to ack the RPC message before
  attempting to process the message (workaround for servers not able
  to process certain requests, maybe a nicer generic soultion can be
  found or it can be made configurable when starting the server)
- Fix exception handling in the example exception logger middleware
- dispatcher.py: Fix mypy warnings annotations for MethodRegistry.add
- package py.typed: mypy stops warning about missing typing infos
- Major update of the aio_pika example server code

1.4.2 (2022-04-14)
------------------

- Added support for Python 3.10
- Fixed missing await for message.ack() in aio_pika.Server
- Fixed using a specific result_queue in aio_pika.Client
  and added examples/aio_pika_client_queue.py to show how to use it.
- Fixed a number of issues in the aio_pika and kombu examples.
- Fixed make test check-code and reduce the amount of issued mypy warnings
- Fixed flask runtime dependency to 2.0 and fix test depends.
- Added a usable extended example with logging in examples/rabbitmq/pika

1.4.1 (2022-03-06)
------------------

- pytest integration fixed to make asynchronous methods pass-through possible.


1.4.0 (2021-11-30)
------------------

- openapi error examples support added.
- openapi errors schema support added.
- multiple extractors support added.
- docstring extractor bug fixed.


1.3.5 (2021-11-03)
------------------

- request and response loggers separated.
- alternative json-rpc content types support added.


1.3.4 (2021-09-11)
------------------

- openapi dataclass alias setting bug fixed.


1.3.3 (2021-09-10)
------------------

- openapi jsonrpc request schema fixed


1.3.2 (2021-08-30)
------------------

- starlette integration added
- django integration added
- sub endpoints support implemented


1.3.1 (2021-08-24)
------------------

- pytest integration bug fixed
- ViewMethod copy bug fixed
- pydantic required version increased
- openapi/openrpc specification definitions support implemented


1.3.0 (2021-08-13)
------------------

- openapi specification generation implemented
- openrpc specification generation implemented
- web ui support added (SwaggerUI, RapiDoc, ReDoc)


1.2.3 (2021-08-10)
------------------

- pydantic schema generation bug fixed
- method registry merge implementation changed


1.2.2 (2021-07-28)
------------------

- pydantic validation schema bug fixed
- method registry merge bug fixed
- method view validation bug fixed
- method metadata format changed


1.2.1 (2021-03-02)
------------------

- some trash removed


1.2.0 (2021-03-01)
------------------

- httpx integration added


1.1.1 (2020-10-25)
------------------

- dependencies updated


1.1.0 (2020-03-28)
------------------

- type annotations added


1.0.0 (2020-03-14)
------------------

- middleware support implemented
- client tracing implemented
- aiohttp server backend refactored
- validation error json serialization fix
- request dispatcher refactored


0.1.4 (2019-12-10)
------------------

- aio-pika and kombu integration refactoring
- async dispatcher concurrent methods execution implemented


0.1.3 (2019-11-10)
------------------

- Some bugs fixed
- Documentation completed


0.1.2 (2019-11-10)
------------------

- Some unit tests added


0.1.1 (2019-11-09)
------------------

- Some minor fixes


0.1.0 (2019-10-23)
------------------

- Initial release
