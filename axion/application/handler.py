import asyncio
import importlib
import inspect
import typing as t

from loguru import logger

from axion import specification

Handler = t.Callable[..., t.Awaitable[t.Any]]


class InvalidHandlerError(Exception):
    ...


class OASHandlerMismatch(Exception):
    ...


def make(operation: specification.OASOperation) -> Handler:
    logger.info('Making user handler for op={op}', op=operation)
    return _analyze(
        _resolve(operation.operation_id),
        operation,
    )


def _resolve(operation_id: str) -> Handler:
    logger.opt(lazy=True).debug(
        'Resolving user handler via operation_id={operation_id}',
        operation_id=lambda: operation_id,
    )

    module_name, function_name = operation_id.rsplit('.', 1)

    try:
        module = importlib.import_module(module_name)
        function = getattr(module, function_name)
        if not asyncio.iscoroutinefunction(function):
            raise InvalidHandlerError(f'{operation_id} did not resolve to coroutine')
    except ImportError as err:
        raise InvalidHandlerError(f'Failed to import module={module_name}') from err
    except AttributeError as err:
        raise InvalidHandlerError(
            f'Failed to locate function={function_name} in module={module_name}',
        ) from err
    else:
        return t.cast(Handler, function)


def _analyze(
        handler: Handler,
        operation: specification.OASOperation,
) -> Handler:
    signature = inspect.signature(handler)

    for op_param in operation.parameters:
        try:
            handler_param = signature.parameters[op_param.name]
            if handler_param.annotation != op_param.python_type:
                raise OASHandlerMismatch(
                    f'{op_param.name} argument of {handler} expected to have '
                    f'type {op_param.python_type}, but in fact it is '
                    f'{handler_param.annotation}',
                )
        except KeyError as err:
            raise OASHandlerMismatch(
                f'{op_param} not found in {handler} arguments',
            ) from err

    return handler
