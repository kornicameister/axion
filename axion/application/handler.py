import asyncio
import importlib
import typing as t

from loguru import logger


class InvalidHandlerError(Exception):
    ...


def resolve(operation_id: str) -> t.Callable[..., t.Awaitable[t.Any]]:
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
        return t.cast(t.Callable[..., t.Awaitable[t.Any]], function)
