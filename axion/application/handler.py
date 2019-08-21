import asyncio
import functools
import importlib
import typing as t

from loguru import logger
import typing_extensions as te

from axion import specification

__all__ = ('InvalidHandlerError', )

Handler = t.Callable[..., t.Awaitable[t.Any]]
T = t.Union[t.Type[t.Any], t.Tuple[t.Type[t.Any], ...]]


class IncorrectTypeReason(t.NamedTuple):
    expected: T
    actual: T

    def __repr__(self) -> str:
        expected_str = _readable_t(self.expected)
        actual_str = _readable_t(self.actual)
        return f'expected {expected_str}, but got {actual_str}'


Reason = t.Union[te.Literal['missing'], IncorrectTypeReason]


class Error(t.NamedTuple):
    param_name: str
    reason: Reason


class InvalidHandlerError(
        ValueError,
        t.Mapping[str, Reason],
):
    __slots__ = (
        '_operation_id',
        '_errors',
    )

    def __init__(
            self,
            operation_id: str,
            errors: t.Optional[t.AbstractSet[Error]] = None,
            message: t.Optional[str] = None,
    ) -> None:
        header_msg = f'\n{operation_id} handler mismatch signature:'
        if errors and not message:
            error_str = '\n'.join(
                f'argument => {m.param_name} : {m.reason}' for m in errors
            )
            message = '\n'.join([
                header_msg,
                error_str,
            ])
            super().__init__(message)

        super().__init__(message)
        self._errors = errors
        self._operation_id = operation_id

    @property
    def operation_id(self) -> str:
        return self._operation_id

    @property
    def errors(self) -> t.Mapping[str, Reason]:
        return {e.param_name: e.reason for e in self._errors or []}

    def __iter__(self) -> t.Iterator[Reason]:  # type: ignore
        return iter(e.reason for e in self._errors or [])

    def __len__(self) -> int:
        return len(self._errors or [])

    def __getitem__(self, key: str) -> Reason:
        return self.errors[key]


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
            raise InvalidHandlerError(
                operation_id=operation_id,
                message=f'{operation_id} did not resolve to coroutine',
            )
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
    else:
        return t.cast(Handler, function)


def _analyze(
        handler: Handler,
        operation: specification.OASOperation,
) -> Handler:
    signature = t.get_type_hints(handler)
    errors = set()

    for op_param in operation.parameters:
        try:
            handler_param = signature[op_param.name]

            handler_param_args = getattr(handler_param, '__args__', handler_param)
            op_param_type_args = _build_annotation_args(op_param)

            if handler_param_args != op_param_type_args:
                errors.add(
                    Error(
                        param_name=op_param.name,
                        reason=IncorrectTypeReason(
                            actual=handler_param_args,
                            expected=op_param_type_args,
                        ),
                    ),
                )
        except KeyError:
            errors.add(
                Error(
                    param_name=op_param.name,
                    reason='missing',
                ),
            )

    if errors:
        logger.error(
            'Collected {count} mismatch error{s} for {op_id} handler',
            count=len(errors),
            op_id=operation.id,
            s='s' if len(errors) > 1 else '',
        )
        raise InvalidHandlerError(
            operation_id=operation.id,
            errors=errors,
        )

    return handler


@functools.lru_cache(maxsize=10)
def _build_annotation_args(param: specification.OASParameter) -> T:
    p_type = param.python_type
    p_required = param.required
    if not p_required:
        return p_type, type(None)
    else:
        return p_type


@functools.lru_cache(maxsize=10)
def _readable_t(val: T) -> str:
    def qualified_name(tt: t.Any) -> str:
        name: str = getattr(tt, '__qualname__', '')
        if not name:
            # there is no name via __qualname__
            # might be that we are dealing with something from typing
            name = repr(tt).replace('~', '')
        return name

    if isinstance(val, tuple):
        last_type = val[-1]
        if issubclass(last_type, type(None)):
            return f'typing.Optional[{",".join(qualified_name(tt) for tt in val[:-1])}]'
        else:
            return f'typing.Union[{",".join(qualified_name(tt) for tt in val)}]]'
    else:
        return f'{qualified_name(val)}'
