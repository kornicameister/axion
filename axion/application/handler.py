import asyncio
import collections
import functools
import importlib
import inspect
import re
import sys
import typing as t

from loguru import logger
from multidict import istr
import typing_extensions as te

from axion import specification

__all__ = (
    'InvalidHandlerError',
    'make',
)

F = t.Callable[..., t.Awaitable[t.Any]]
T = t.Any

OAS_Param = t.NamedTuple(
    'OAS_Param',
    (
        ('param_in', specification.OASParameterLocation),
        ('param_name', str),
    ),
)
F_Param = t.NewType('F_Param', str)
ParamMapping = t.Mapping[OAS_Param, F_Param]

CamelCaseToSnakeCaseRegex = re.compile(r'(?!^)(?<!_)([A-Z])')


@te.final
class Handler(t.NamedTuple):
    fn: F
    param_mapping: ParamMapping

    @property
    def path_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('path')

    @property
    def header_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('header')

    @property
    def query_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('query')

    def _params(
            self,
            param_in: specification.OASParameterLocation,
    ) -> t.FrozenSet[t.Tuple[str, str]]:
        gen = ((oas_param.param_name, fn_param)
               for oas_param, fn_param in self.param_mapping.items()
               if oas_param.param_in == param_in)
        return frozenset(gen)


class IncorrectTypeReason:
    expected: t.List[T]
    actual: T

    def __init__(self, expected: t.List[T], actual: T) -> None:
        self.expected = expected
        self.actual = actual

    def __repr__(self) -> str:
        expected_str = ','.join(_readable_t(rt) for rt in self.expected)
        actual_str = _readable_t(self.actual)
        return f'expected [{expected_str}], but got {actual_str}'


class DuplicatedArgumentReason(t.NamedTuple):
    first_found_in: specification.OASParameterLocation
    duplicated_in: specification.OASParameterLocation

    def __repr__(self) -> str:
        return f'in {self.first_found_in} duplicated by {self.duplicated_in}'


Reason = t.Union[te.Literal['missing', 'unknown'],
                 DuplicatedArgumentReason,
                 IncorrectTypeReason,
                 ]


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
                f'argument {m.param_name} :: {m.reason}' for m in errors
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
    def reasons(self) -> t.Mapping[str, Reason]:
        return {e.param_name: e.reason for e in self._errors or []}

    def __iter__(self) -> t.Iterator[Error]:  # type: ignore
        return iter(e for e in self._errors or [])

    def __len__(self) -> int:
        return len(self._errors or [])

    def __getitem__(self, key: str) -> Reason:
        return self.reasons[key]


def make(operation: specification.OASOperation) -> Handler:
    logger.opt(record=True).info('Making user handler for op={op}', op=operation)
    return _analyze(
        _resolve(operation.id),
        operation,
    )


def _resolve(operation_id: specification.OASOperationId) -> F:
    logger.opt(
        lazy=True,
        record=True,
    ).debug(
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
        return t.cast(F, function)


def _analyze(
        handler: F,
        operation: specification.OASOperation,
) -> Handler:
    signature = t.get_type_hints(handler)

    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    if operation.parameters:

        pq_errors, pq_params = _analyze_path_query(
            specification.operation_filter_parameters(operation, 'path', 'query'),
            signature,
        )
        h_errors, h_params = _analyze_headers(
            specification.operation_filter_parameters(operation, 'header'),
            signature,
        )

        errors.update(pq_errors, h_errors)
        param_mapping.update(pq_params)
        param_mapping.update(h_params)
    else:
        logger.opt(
            lazy=True,
            record=True,
        ).debug(
            '{op_id} does not declare any parameters',
            op_id=lambda: operation.id,
        )

    if errors:
        logger.opt(record=True).error(
            'Collected {count} mismatch error{s} for {op_id} handler',
            count=len(errors),
            op_id=operation.id,
            s='s' if len(errors) > 1 else '',
        )
        raise InvalidHandlerError(
            operation_id=operation.id,
            errors=errors,
        )

    return Handler(
        fn=handler,
        param_mapping=param_mapping,
    )


def _analyze_headers(
        parameters: t.Sequence[specification.OASParameter],
        signature: t.Dict[str, t.Any],
) -> t.Tuple[t.Set[Error], ParamMapping]:
    """Analyzes signature of the handler against the headers.

    axion supports defining headers in signature using:
    - typing_extensions.TypedDict
    - typing.Mapping
    - Any other type is rejected with appropriate error.

    Also, when parsing the signature along with operation, following is taken
    into account:
    1. function doest not have "headers" argument and there are no custom OAS headers
        - OK
    2. function doest not have "headers" argument and there are custom OAS headers
        - Warning
        - If there are custom headers defined user ought to specify them
          in signature. There was a point to put them inside there after all.
          However they might be used by a middleware or something, not necessarily
          handler. The warning is the only reliable thing to say.
    3. function has "headers" argument and there no custom OAS headers ->
        - OK
        - User might want to get a hold with headers like "Content-Type"
        - With Mapping all reserved headers go in
        - With TypedDict we must see if users wants one of reserved headers
          Only reserved headers are allowed to be requested for.
    4. function has "headers" argument and there are customer OAS headers
        - OK
        - With Mapping all reserved headers + OAS headers go in
        - With TypedDict allowed keys covers
            - one or more of reserved headers
            - all of OAS headers with appropriate types

    See link bellow for information on reserved header
    https://swagger.io/docs/specification/describing-parameters/#header-parameters
    """
    headers_arg = signature.get('headers')
    has_param_headers = len(parameters) > 0

    if headers_arg is not None:
        # pre-check type of headers param in signature
        # must be either TypedDict, Mapping or a subclass of those
        is_mapping, is_any = _is_headers_arg_dict_like(headers_arg)
        if not (is_mapping or is_any):
            return {
                Error(
                    param_name='headers',
                    reason=IncorrectTypeReason(
                        actual=headers_arg,
                        expected=[
                            t.Mapping[str, t.Any],
                            t.Dict[str, t.Any],
                            te.TypedDict,
                        ],
                    ),
                ),
            }, {}
        elif is_any:
            logger.opt(record=True).warning(
                'Detected usage of "headers" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
        if has_param_headers:
            return _analyze_headers_signature_set_oas_set(
                parameters=parameters,
                headers_arg=headers_arg,
            )
        else:
            return _analyze_headers_signature_set_oas_gone(headers_arg)
    elif has_param_headers:
        return _analyze_headers_signature_gone_oas_set()
    else:
        return _analyze_headers_signature_gone_oas_gone()


def _analyze_headers_signature_gone_oas_gone() -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).debug('No "headers" in signature and operation parameters')
    return set(), {}


def _analyze_headers_signature_gone_oas_set() -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).warning(
        '"headers" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "headers" defined in '
        'specification, they have to be present in your handler '
        'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
        'or typing_extensions.TypedDict[str, typing.Any].',
    )
    return set(), {}


def _analyze_headers_signature_set_oas_gone(
        headers_arg: t.Any,
) -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(
        record=True,
        lazy=True,
    ).debug('"headers" found in signature but not in operation')

    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    try:
        # deal with typed dict, only reserved headers are allowed as dict
        reserved_headers_keys = {
            _get_f_param(rh): rh.lower()
            for rh in specification.OASReservedHeaders
        }
        entries = t.get_type_hints(headers_arg).items()
        if entries:
            for hdr_param_name, hdr_param_type in entries:
                if hdr_param_name not in reserved_headers_keys:
                    logger.opt(record=True).error(
                        '{sig_key} is not one of {reserved_headers} headers',
                        sig_key=hdr_param_name,
                        reserved_headers=specification.OASReservedHeaders,
                    )
                    errors.add(
                        Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason='unknown',
                        ),
                    )
                elif hdr_param_type != str:
                    errors.add(
                        Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason=IncorrectTypeReason(
                                actual=hdr_param_type,
                                expected=[str],
                            ),
                        ),
                    )
                else:
                    param_key = _get_f_param(hdr_param_name)
                    param_mapping[OAS_Param(
                        param_in='header',
                        param_name=reserved_headers_keys[param_key],
                    )] = param_key
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        # deal with mapping: in that case user will receive all
        # reserved headers inside of the handler
        for hdr in specification.OASReservedHeaders:
            param_mapping[OAS_Param(
                param_in='header',
                param_name=hdr.lower(),
            )] = _get_f_param(hdr)

    return errors, param_mapping


def _analyze_headers_signature_set_oas_set(
        parameters: t.Sequence[specification.OASParameter],
        headers_arg: t.Any,
) -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).debug('"headers" found both in signature and operation')

    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    param_headers: t.Dict[F_Param, str] = {
        _get_f_param(rh.name): rh.name
        for rh in parameters
    }
    reserved_headers: t.Dict[F_Param, str] = {
        _get_f_param(rh): rh
        for rh in specification.OASReservedHeaders
    }
    all_headers_names = {**param_headers, **reserved_headers}

    try:
        entries = t.get_type_hints(headers_arg).items()
        if entries:
            for hdr_param_name, hdr_param_type in entries:
                if hdr_param_name in all_headers_names:
                    # now tricky part, for reserved headers we enforce str
                    # for oas headers we do type check
                    if hdr_param_name in reserved_headers and hdr_param_type != str:
                        errors.add(
                            Error(
                                param_name=f'headers.{hdr_param_name}',
                                reason=IncorrectTypeReason(
                                    actual=hdr_param_type,
                                    expected=[str],
                                ),
                            ),
                        )
                        continue
                    elif hdr_param_name in param_headers:
                        oas_param = next(
                            filter(
                                lambda p: p.name == param_headers[
                                    _get_f_param(hdr_param_name)],
                                parameters,
                            ),
                        )
                        oas_param_type = _build_annotation_args(oas_param)
                        if oas_param_type != hdr_param_type:
                            errors.add(
                                Error(
                                    param_name=f'headers.{hdr_param_name}',
                                    reason=IncorrectTypeReason(
                                        actual=hdr_param_type,
                                        expected=[str],
                                    ),
                                ),
                            )
                            continue

                    param_mapping[OAS_Param(
                        param_in='header',
                        param_name=all_headers_names[_get_f_param(
                            hdr_param_name,
                        )].lower(),
                    )] = _get_f_param(hdr_param_name)

                else:
                    errors.add(
                        Error(
                            param_name=f'headers.{hdr_param_name}',
                            reason='unknown',
                        ),
                    )
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        for hdr_param_name, hdr_param_type in all_headers_names.items():
            param_mapping[OAS_Param(
                param_in='header',
                param_name=hdr_param_type.lower(),
            )] = hdr_param_name

    return errors, param_mapping


def _is_headers_arg_dict_like(sig_headers: t.Any) -> t.Tuple[bool, bool]:
    maybe_name = getattr(sig_headers, '_name', None)
    maybe_supertype = getattr(sig_headers, '__supertype__', None)
    maybe_mro = getattr(sig_headers, '__mro__', None)
    if maybe_name:
        # raw typing.Dict or typing.Mapping
        return maybe_name in ('Mapping', 'Dict'), maybe_name.lower() == 'any'
    elif maybe_supertype:
        # typing.NewType
        return _is_headers_arg_dict_like(maybe_supertype)
    elif maybe_mro:
        for mro in inspect.getmro(sig_headers):
            if issubclass(mro, (dict, collections.abc.Mapping)):
                return True, False
    elif sys.version_info < (3, 7):
        return False, sig_headers is t.Any

    return False, False


def _analyze_path_query(
        parameters: t.Sequence[specification.OASParameter],
        signature: t.Dict[str, t.Any],
) -> t.Tuple[t.Set[Error], ParamMapping]:
    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    for op_param in parameters:
        try:
            handler_param_name = _get_f_param(op_param.name)
            handler_param = signature[handler_param_name]

            handler_param_args = getattr(handler_param, '__args__', handler_param)
            op_param_type_args = _build_annotation_args(op_param)

            if handler_param_args != op_param_type_args:
                errors.add(
                    Error(
                        param_name=op_param.name,
                        reason=IncorrectTypeReason(
                            actual=handler_param_args,
                            expected=[op_param_type_args],
                        ),
                    ),
                )
            else:
                key = OAS_Param(
                    param_in=specification.parameter_in(op_param),
                    param_name=op_param.name,
                )
                if key not in param_mapping.values():
                    param_mapping[key] = handler_param_name
                else:
                    errors.add(
                        Error(
                            param_name=op_param.name,
                            reason=DuplicatedArgumentReason(
                                first_found_in=next(
                                    filter(
                                        lambda pk: pk.param_name == op_param.name,
                                        param_mapping.keys(),
                                    ),
                                ).param_in,
                                duplicated_in=key.param_in,
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

    return errors, param_mapping


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
        the_name = str(tt)
        if 'typing.' in the_name:
            return the_name
        else:
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
            return f'typing.Union[{",".join(qualified_name(tt) for tt in val)}]'
    else:
        return f'{qualified_name(val)}'


@functools.lru_cache(maxsize=100)
def _get_f_param(s: t.Union[str, istr]) -> F_Param:
    return F_Param(CamelCaseToSnakeCaseRegex.sub(r'_\1', s.replace('-', '_')).lower())
