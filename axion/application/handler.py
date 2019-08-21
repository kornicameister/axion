import asyncio
import importlib
import typing as t
import functools

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
        _resolve(operation.id),
        operation,
    )


def _resolve(operation_id: specification.OASOperationId) -> Handler:
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
    signature = t.get_type_hints(handler)
    for op_param in operation.parameters:
        try:
            handler_param = signature[op_param.name]

            handler_param_args = getattr(handler_param, '__args__', handler_param)
            op_param_type_args = _build_annotation_args(op_param)

            if handler_param_args != op_param_type_args:
                raise OASHandlerMismatch(
                    f'{op_param.name} argument of {handler} expected to have '
                    f'type {op_param_type_args}, but in fact it is '
                    f'{handler_param}',
                )
        except KeyError as err:
            raise OASHandlerMismatch(
                f'{op_param} not found in {handler} arguments',
            ) from err

    return handler


@functools.lru_cache(maxsize=10)
def _build_annotation_args(
        param: specification.OASParameter,
) -> t.Union[t.Type[t.Any], t.Tuple[t.Type[t.Any], ...]]:
    p_type = param.python_type
    p_required = param.required
    if not p_required:
        return p_type, type(None)
    else:
        return p_type
