import asyncio
import functools
import importlib
import typing as t

from loguru import logger
import typing_extensions as te

from axion import oas
from axion.handler import analysis
from axion.handler import model
from axion.handler.exceptions import (
    InvalidHandlerError,
)
from axion.utils import types


@t.overload
def resolve(
    operation: oas.OASOperation,
    *,
    request_processor: model.AsyncRequestProcessor[model.RQ],
    response_processor: model.AsyncResponseProcessor[model.RP],
    asynchronous: te.Literal[True] = True,
) -> model.AsyncHandler[model.RQ, model.RP]:
    ...  # pragma: no cover


@t.overload
def resolve(
    operation: oas.OASOperation,
    *,
    request_processor: model.SyncRequestProcessor[model.RQ],
    response_processor: model.SyncResponseProcessor[model.RP],
    asynchronous: te.Literal[False] = False,
) -> model.SyncHandler[model.RQ, model.RP]:
    ...  # pragma: no cover


def resolve(
    operation: oas.OASOperation,
    *,
    request_processor: types.AnyCallable,
    response_processor: types.AnyCallable,
    asynchronous: bool = False,
) -> model.Handler:
    logger.info('Making user handler for op={op}', op=operation)
    return _resolve(
        _import(
            operation.id,
            asynchronous=asynchronous,
        ),
        operation,
        request_processor=request_processor,
        response_processor=response_processor,
    )


@functools.lru_cache()
def _resolve(
    handler: model.UF,
    operation: oas.OASOperation,
    *,
    request_processor: types.AnyCallable,
    response_processor: types.AnyCallable,
) -> model.Handler:
    analysis_result = analysis.analyze(handler, operation)

    handler_cls = (
        model.AsyncHandler if asyncio.iscoroutinefunction(handler) else model.SyncHandler
    )  # type: t.Type[model.Handler]

    return handler_cls(
        param_mapping=analysis_result.param_mapping,
        has_body=analysis_result.has_body,
        user_handler=handler,
        request_processor=request_processor,
        response_processor=response_processor,
    )


def _import(
    operation_id: oas.OASOperationId,
    asynchronous: bool,
) -> types.AnyCallable:
    logger.debug(
        'Resolving user handler via operation_id={id}',
        id=operation_id,
    )

    module_name, function_name = operation_id.rsplit('.', 1)
    function: types.AnyCallable

    try:
        module = importlib.import_module(module_name)
        function = getattr(module, function_name)

        if asynchronous:
            if not asyncio.iscoroutinefunction(function):
                raise InvalidHandlerError(
                    operation_id=operation_id,
                    message=f'{operation_id} did not resolve to coroutine',
                )

        logger.opt(lazy=True).debug(
            'Found {type} handler for operation {id}',
            id=lambda: operation_id,
            type=lambda: 'asynchronous' if asynchronous else 'synchronous',
        )

        return function
    except ImportError as err:
        raise InvalidHandlerError(
            operation_id=operation_id,
            message=f'Failed to import module={module_name}',
        ) from err
    except AttributeError as err:
        raise InvalidHandlerError(
            operation_id=operation_id,
            message=f'Failed to locate function={function_name} in module={module_name}',
        ) from err


__all__ = (
    'resolve',
    'InvalidHandlerError',
)
