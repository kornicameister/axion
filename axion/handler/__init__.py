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

LOG: te.Final = logger.opt(lazy=True)


@t.overload
def resolve(
    operation: oas.OASOperation,
    asynchronous: te.Literal[True],
) -> model.AsyncHandler:
    ...  # pragma: no cover


@t.overload
def resolve(
    operation: oas.OASOperation,
    asynchronous: te.Literal[False],
) -> model.SyncHandler:
    ...  # pragma: no cover


def resolve(
    operation: oas.OASOperation,
    asynchronous: bool,
) -> model.Handler[types.AnyCallable]:
    LOG.info(
        'Making user handler for op={op}',
        op=lambda: operation,
    )
    return _resolve(_import(operation.id, asynchronous), operation)


def _resolve(
    handler: types.AnyCallable,
    operation: oas.OASOperation,
) -> model.Handler[types.AnyCallable]:
    analysis_result = analysis.analyze(handler, operation)

    handler_cls = (
        model.AsyncHandler if asyncio.iscoroutinefunction(handler) else model.SyncHandler
    )  # type: t.Type[model.Handler[types.AnyCallable]]

    return handler_cls(
        fn=handler,
        param_mapping=analysis_result.param_mapping,
        has_body=analysis_result.has_body,
    )


@functools.lru_cache()
def _import(
    operation_id: oas.OASOperationId,
    asynchronous: bool,
) -> types.AnyCallable:
    LOG.debug(
        'Resolving user handler via operation_id={operation_id}',
        operation_id=lambda: operation_id,
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

            LOG.debug(
                'Found asynchronous handler for operation {id}',
                id=lambda: operation_id,
            )
        else:
            LOG.debug(
                'Found synchronous handler for operation {id}',
                id=lambda: operation_id,
            )  # pragma: no cover

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
