import asyncio
from dataclasses import dataclass
import functools
import importlib
import re
import sys
import typing as t

from loguru import logger
from multidict import istr
import pampy as pm
import typing_extensions as te
import typing_inspect as ti

from axion import oas
from axion import response
from axion.utils import get_type_repr
from axion.utils import types

__all__ = (
    'InvalidHandlerError',
    'make',
)

F = t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]
T = t.Any

OAS_Param = t.NamedTuple(
    'OAS_Param',
    (
        ('param_in', oas.OASParameterLocation),
        ('param_name', str),
    ),
)
F_Param = t.NewType('F_Param', str)
ParamMapping = t.Mapping[OAS_Param, F_Param]

CamelCaseToSnakeCaseRegex = re.compile(r'(?!^)(?<!_)([A-Z])')

BODY_TYPES: te.Final = [
    t.Mapping[str, t.Any],
    t.Dict[str, t.Any],
]
COOKIES_HEADERS_TYPE: te.Final = [
    t.Mapping[str, t.Any],
    t.Dict[str, t.Any],
    te.TypedDict,
]
HTTP_CODE_TYPE: te.Final = int

AXION_RESPONSE_ENTRIES: te.Final = getattr(response.Response, '__annotations__', {})
AXION_RESPONSE_KEYS: te.Final = frozenset(AXION_RESPONSE_ENTRIES.keys())

if sys.version_info >= (3, 8):
    cached_property = functools.cached_property
else:
    from cached_property import cached_property


@te.final
@dataclass(frozen=True, repr=True)
class Handler:
    fn: F
    has_body: bool
    param_mapping: ParamMapping

    @cached_property
    def path_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('path')

    @cached_property
    def header_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('header')

    @cached_property
    def query_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('query')

    @cached_property
    def cookie_params(self) -> t.FrozenSet[t.Tuple[str, str]]:
        return self._params('cookie')

    def _params(
            self,
            param_in: oas.OASParameterLocation,
    ) -> t.FrozenSet[t.Tuple[str, str]]:
        gen = ((oas_param.param_name, fn_param)
               for oas_param, fn_param in self.param_mapping.items()
               if oas_param.param_in == param_in)
        return frozenset(gen)


class IncorrectTypeReason:
    expected: t.Sequence[T]
    actual: T

    def __init__(self, expected: t.Sequence[T], actual: T) -> None:
        self.expected = expected
        self.actual = actual

    def __repr__(self) -> str:
        expected_str = ','.join(get_type_repr.get_repr(rt) for rt in self.expected)
        actual_str = get_type_repr.get_repr(self.actual)
        return f'expected [{expected_str}], but got {actual_str}'


CustomReason = t.NewType('CustomReason', str)
CommonReasons = te.Literal['missing', 'unexpected', 'unknown']
Reason = t.Union[CommonReasons, IncorrectTypeReason, CustomReason]


class Error(t.NamedTuple):
    reason: Reason
    param_name: str


@te.final
class InvalidHandlerError(
        ValueError,
        t.Mapping[str, str],
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
            super().__init__('\n'.join([
                header_msg,
                error_str,
            ]))
        else:
            super().__init__(message)

        self._errors = frozenset(errors or [])
        self._operation_id = operation_id

    @property
    def operation_id(self) -> str:
        return self._operation_id

    @property
    def reasons(self) -> t.Mapping[str, str]:
        return {e.param_name: str(e.reason) for e in self._errors or []}

    def __iter__(self) -> t.Iterator[Error]:  # type: ignore
        return iter(e for e in self._errors or [])

    def __len__(self) -> int:
        return len(self._errors or [])

    def __getitem__(self, key: str) -> str:
        return self.reasons[key]

    def __repr__(self) -> str:
        repr_reasons = (f'{k}: {v}' for k, v in self.reasons.items())
        return f'InvalidHandlerError :: {", ".join(repr_reasons)}'


def make(operation: oas.OASOperation) -> Handler:
    logger.opt(record=True).info('Making user handler for op={op}', op=operation)
    return _build(
        _resolve(operation.id),
        operation,
    )


def _resolve(operation_id: oas.OASOperationId) -> F:
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


def _build(
        handler: F,
        operation: oas.OASOperation,
) -> Handler:
    signature = t.get_type_hints(handler)

    errors, has_body = _analyze_request_body(
        operation.request_body,
        signature.pop('body', None),
    )
    rt_errors = _analyze_return_type(
        operation,
        signature,
    )

    errors.update(rt_errors)
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    if operation.parameters:
        h_errors, h_params = _analyze_headers(
            oas.operation_filter_parameters(operation, 'header'),
            signature.pop('headers', None),
        )
        c_errors, c_params = _analyze_cookies(
            oas.operation_filter_parameters(operation, 'cookie'),
            signature.pop('cookies', None),
        )
        pq_errors, pq_params = _analyze_path_query(
            oas.operation_filter_parameters(operation, 'path', 'query'),
            signature,
        )

        if signature:
            logger.opt(record=True).error(
                'Unconsumed arguments [{args}] detected in {op_id} handler signature',
                op_id=operation.id,
                args=', '.join(arg_key for arg_key in signature.keys()),
            )
            errors.update(
                Error(
                    param_name=arg_key,
                    reason='unexpected',
                ) for arg_key in signature.keys()
            )

        errors.update(pq_errors, h_errors, c_errors)
        param_mapping.update(pq_params)
        param_mapping.update(h_params)
        param_mapping.update(c_params)
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
        has_body=has_body,
    )


def _analyze_return_type(
        operation: oas.OASOperation,
        signature: t.Dict[str, t.Any],
) -> t.Set[Error]:

    if 'return' not in signature:
        logger.opt(
            record=True,
            lazy=True,
        ).error(
            'Operation {id} handler does not define return annotation',
            id=lambda: operation.id,
        )
        return {Error(param_name='return', reason='missing')}
    else:
        return_type = signature.pop('return')
        rt_entries = getattr(return_type, '__annotations__', {}).copy()
        matching_keys = AXION_RESPONSE_KEYS.intersection(set(rt_entries.keys()))

        logger.opt(
            record=True,
            lazy=True,
        ).debug(
            'Operation {id} handler defines [{keys}] in return type',
            id=lambda: operation.id,
            keys=lambda: ','.join(rt_entries.keys()),
        )

        if matching_keys:
            return {
                *_analyze_return_type_http_code(
                    operation,
                    rt_entries.pop('http_code', None),
                ),
                *_analyze_return_type_cookies(
                    operation,
                    rt_entries.pop('cookies', None),
                ),
                *_analyze_return_type_headers(
                    operation,
                    rt_entries.pop('headers', None),
                ),
                *_analyze_return_type_body(
                    operation,
                    rt_entries.pop('body', None),
                ),
            }
        else:
            logger.opt(
                record=True,
                lazy=True,
            ).error(
                'Operation {id} handler return type is incorrect, '
                'expected {expected_type} but received {actual_type}',
                id=lambda: operation.id,
                expected_type=lambda: response.Response,
                actual_type=lambda: return_type,
            )
            return {
                Error(
                    param_name='return',
                    reason=IncorrectTypeReason(
                        expected=[response.Response],
                        actual=return_type,
                    ),
                ),
            }


def _analyze_return_type_headers(
        operation: oas.OASOperation,
        headers: t.Optional[t.Type[t.Any]],
) -> t.Set[Error]:
    if headers is not None and not types.is_dict_like(headers):
        return {
            Error(
                param_name=f'return.headers',
                reason=IncorrectTypeReason(
                    expected=COOKIES_HEADERS_TYPE,
                    actual=headers,
                ),
            ),
        }
    return set()


def _analyze_return_type_body(
        operation: oas.OASOperation,
        body: t.Optional[t.Type[t.Any]],
) -> t.Set[Error]:

    def _is_arg_body_none() -> bool:
        return any((
            body is None,
            types.is_none_type(body),
            ti.is_literal_type(body) and ti.get_args(body, ti.NEW_TYPING)[0] is None,
        ))

    def _body_must_be_empty(__: t.Any) -> t.Set[Error]:
        logger.opt(
            lazy=True,
            record=True,
        ).error(
            'Operation {id} handler defines return.body but '
            'having only 204 response defined makes it impossible to return '
            'any body.',
            id=lambda: operation.id,
        )
        return {
            Error(
                param_name=f'return.body',
                reason=CustomReason(
                    'OAS defines single response with 204 code. '
                    'Returning http body in such case is not possible.',
                ),
            ),
        }

    match_input = (list(operation.responses.keys()), _is_arg_body_none())
    errors: t.Set[Error] = pm.match(
        match_input,
        # yapf: disable
        ([204], True), set(),
        ([204], False), _body_must_be_empty,
        pm._, set(),
        # yapf: enable
    )
    logger.opt(
        record=True,
        lazy=True,
    ).error(
        'Operation handler {id} produced {err} error{s} over an input {mi}',
        id=lambda: operation.id,
        s=lambda: '' if len(errors) else 's',
        mi=lambda: match_input,
        err=lambda: len(errors),
    )
    return errors

    assert False, 'this should not happen'

    if body is None:
        ...
    elif types.is_none_type(body):
        ...
    elif types.is_new_type(body):
        return _analyze_return_type_body(
            operation,
            body.__supertype__,
        )
    elif types.is_any_type(body):
        logger.opt(
            lazy=True,
            record=True,
        ).warning(
            'Operation {id} handler defined return.body as {any}. '
            'axion permits that but be warned that you loose entire support '
            'from linters (i.e. mypy)',
            id=lambda: operation.id,
            any=lambda: repr(t.Any),
        )
        return set()
    elif ti.is_literal_type(body):
        body_args = ti.get_args(body, ti.NEW_TYPING)
        if len(body_args) == 1:
            return _analyze_return_type_body(
                operation,
                body_args[0],
            )
        return set()
    else:
        if all((
                len(operation.responses),
                204 in operation.responses,
        )):
            logger.opt(
                lazy=True,
                record=True,
            ).error(
                'Operation {id} handler defines return.body but '
                'having only 204 response defined makes it impossible to return '
                'any body.',
                id=lambda: operation.id,
            )
            return {
                Error(
                    param_name=f'return.body',
                    reason=CustomReason(
                        'OAS defines single response with 204 code. '
                        'Returning http body in such case is not possible.',
                    ),
                ),
            }
        elif not types.is_dict_like(body):
            return {
                Error(
                    param_name=f'return.body',
                    reason=IncorrectTypeReason(
                        expected=BODY_TYPES,
                        actual=body,
                    ),
                ),
            }

    return set()


def _analyze_return_type_cookies(
        operation: oas.OASOperation,
        cookies: t.Optional[t.Type[t.Any]],
) -> t.Set[Error]:
    if cookies is not None and not types.is_dict_like(cookies):
        return {
            Error(
                param_name=f'return.cookies',
                reason=IncorrectTypeReason(
                    expected=COOKIES_HEADERS_TYPE,
                    actual=cookies,
                ),
            ),
        }
    return set()


def _analyze_return_type_http_code(
        operation: oas.OASOperation,
        rt_http_code: t.Optional[t.Type[t.Any]],
) -> t.Set[Error]:

    if rt_http_code is None:
        # if there's no http_code in return Response
        # this is permitted only if there's single response defined in
        # OAS responses. User needs to set it otherwise how can we tell if
        # everything is correct
        if len(operation.responses) != 1:
            logger.opt(
                lazy=True,
                record=True,
            ).error(
                'Operation {id} handler skips return.http_code but it is impossible '
                ' with {count_of_ops} responses due to ambiguity.',
                id=lambda: operation.id,
                count_of_ops=lambda: len(operation.responses),
            )
            return {Error(
                param_name='return.http_code',
                reason='missing',
            )}
        return set()

    elif ti.is_literal_type(rt_http_code):
        # this is acceptable. Literals hold particular values inside of them
        # if user wants to have it that way -> go ahead.
        # axion however will not validate a specific values in Literal.
        # this is by design and due to:
        # - error responses that axion implements via exceptions
        literal_types = types.literal_types(rt_http_code)
        if not all(issubclass(lmt, HTTP_CODE_TYPE) for lmt in literal_types):
            return {
                Error(
                    param_name='return.http_code',
                    reason=CustomReason(f'expected {repr(te.Literal)}[int]'),
                ),
            }
        return set()

    elif types.is_new_type(rt_http_code):
        # not quite sure why user would like to alias that
        # but it is not a problem for axion as long `NewType` embedded type
        # is fine
        return _analyze_return_type_http_code(operation, rt_http_code.__supertype__)

    elif issubclass(rt_http_code, bool):
        # yeah, Python rocks -> bool is subclass of an int
        # not quite sure wh that happens, perhaps someone sometime
        # will answer that question
        return {
            Error(
                param_name='return.http_code',
                reason=IncorrectTypeReason(
                    expected=[HTTP_CODE_TYPE],
                    actual=bool,
                ),
            ),
        }
    else:

        try:
            assert issubclass(rt_http_code, HTTP_CODE_TYPE)
            return set()
        except (AssertionError, TypeError):
            ...
        return {
            Error(
                param_name='return.http_code',
                reason=IncorrectTypeReason(
                    actual=rt_http_code,
                    expected=[
                        type(None),
                        HTTP_CODE_TYPE,
                        t.NewType('HttpCode', HTTP_CODE_TYPE),
                        te.Literal,
                    ],
                ),
            ),
        }


def _analyze_request_body(
        request_body: t.Optional[oas.OASRequestBody],
        body_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[Error], bool]:
    if body_arg is None:
        if request_body is None:
            return _analyze_body_signature_gone_oas_gone()
        else:
            return _analyze_body_signature_gone_oas_set()
    else:
        if request_body is None:
            return _analyze_body_signature_set_oas_gone()
        else:
            return _analyze_body_signature_set_oas_set(
                request_body=request_body,
                body_arg=body_arg,
            )


def _analyze_body_signature_set_oas_set(
        request_body: oas.OASRequestBody,
        body_arg: t.Type[t.Any],
) -> t.Tuple[t.Set[Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).trace(
        'Operation defines both request body and argument handler',
    )
    is_body_required = request_body.required
    is_body_arg_required = not ti.is_optional_type(body_arg)

    if is_body_required and not is_body_arg_required:
        return {
            Error(
                param_name='body',
                reason=IncorrectTypeReason(
                    actual=body_arg,
                    expected=BODY_TYPES,
                ),
            ),
        }, True
    return set(), True


def _analyze_body_signature_set_oas_gone() -> t.Tuple[t.Set[Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).error(
        'Operation does not define a request body, but it is '
        'specified in handler signature.',
    )
    return {
        Error(
            param_name='body',
            reason='unexpected',
        ),
    }, False


def _analyze_body_signature_gone_oas_gone() -> t.Tuple[t.Set[Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).trace(
        'Operation does not define a request body',
    )
    return set(), False


def _analyze_body_signature_gone_oas_set() -> t.Tuple[t.Set[Error], bool]:
    logger.opt(
        lazy=True,
        record=True,
    ).error(
        'Operation defines a request body, but it is not specified in '
        'handler signature',
    )
    return {
        Error(
            param_name='body',
            reason='missing',
        ),
    }, True


def _analyze_cookies(
        parameters: t.Sequence[oas.OASParameter],
        cookies_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[Error], ParamMapping]:
    """Analyzes signature of the handler against the cookies.

    axion supports defining cookies in signature using:
    - typing_extensions.TypedDict
    - typing.Mapping
    - typing.Dict
    - Any other type is rejected with appropriate error.

    Also, when parsing the signature along with operation, following is taken
    into account:
    1. function does not have "cookies" argument and there are no custom OAS cookies
        - OK
    2. function has "cookies" argument and there no custom OAS cookies ->
        - Error
    3. function does not have "cookies" argument and there are custom OAS cookies
        - Warning
        - If there are custom cookies defined user ought to specify them
          in signature. There was a point to put them inside there after all.
          However they might be used by a middleware or something, not necessarily
          handler. The warning is the only reliable thing to say.
    4. function has "cookies" argument and there are customer OAS cookies
        - OK
        - With Mapping/Dict all parameters go as they are defined in operation
        - With TypedDict allowed keys are only those defined in operation
    """
    has_param_cookies = len(parameters) > 0

    if cookies_arg is not None:
        # pre-check type of headers param in signature
        # must be either TypedDict, Mapping, Dict or a subclass of those
        is_mapping, is_any = (
            types.is_dict_like(cookies_arg),
            types.is_any_type(cookies_arg),
        )
        if not (is_mapping or is_any):
            return {
                Error(
                    param_name='cookies',
                    reason=IncorrectTypeReason(
                        actual=cookies_arg,
                        expected=COOKIES_HEADERS_TYPE,
                    ),
                ),
            }, {}
        elif is_any:
            logger.opt(record=True).warning(
                'Detected usage of "cookies" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
        if has_param_cookies:
            return _analyze_cookies_signature_set_oas_set(
                parameters=parameters,
                cookies_arg=cookies_arg,
            )
        else:
            return _analyze_cookies_signature_set_oas_gone(cookies_arg)
    elif has_param_cookies:
        return _analyze_cookies_signature_gone_oas_set()
    else:
        return _analyze_cookies_signature_gone_oas_gone()


def _analyze_cookies_signature_gone_oas_gone() -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).debug('No "cookies" in signature and operation parameters')
    return set(), {}


def _analyze_cookies_signature_gone_oas_set() -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).warning(
        '"cookies" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "cookies" defined in '
        'specification, they have to be present in your handler '
        'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
        'or typing_extensions.TypedDict[str, typing.Any].',
    )
    return set(), {}


def _analyze_cookies_signature_set_oas_gone(
        cookies_arg: t.Any,
) -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(
        record=True,
        lazy=True,
    ).error('"cookies" found in signature but not in operation')
    return {
        Error(
            param_name='cookies',
            reason='unexpected',
        ),
    }, {}


def _analyze_cookies_signature_set_oas_set(
        parameters: t.Sequence[oas.OASParameter],
        cookies_arg: t.Any,
) -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).debug('"cookies" found both in signature and operation')

    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    param_cookies: t.Dict[F_Param,
                          str] = {_get_f_param(rh.name): rh.name
                                  for rh in parameters}

    try:
        entries = t.get_type_hints(cookies_arg).items()
        if entries:
            for cookie_param_name, cookie_param_type in entries:
                if cookie_param_name in param_cookies:

                    oas_param = next(
                        filter(
                            lambda p: p.name == param_cookies[
                                _get_f_param(cookie_param_name)],
                            parameters,
                        ),
                    )
                    oas_param_type = _build_type_from_oas_param(oas_param)
                    if oas_param_type != cookie_param_type:
                        errors.add(
                            Error(
                                param_name=f'cookies.{cookie_param_name}',
                                reason=IncorrectTypeReason(
                                    actual=cookie_param_type,
                                    expected=[oas_param_type],
                                ),
                            ),
                        )
                    else:
                        param_mapping[OAS_Param(
                            param_in='cookie',
                            param_name=param_cookies[_get_f_param(
                                cookie_param_name,
                            )].lower(),
                        )] = _get_f_param(cookie_param_name)

                else:
                    errors.add(
                        Error(
                            param_name=f'cookies.{cookie_param_name}',
                            reason='unknown',
                        ),
                    )
        else:
            raise TypeError(
                'Not TypedDict to jump into exception below. '
                'This is 3.6 compatibility action.',
            )
    except TypeError:
        for hdr_param_name, hdr_param_type in param_cookies.items():
            param_mapping[OAS_Param(
                param_in='cookie',
                param_name=hdr_param_type.lower(),
            )] = hdr_param_name

    return errors, param_mapping


def _analyze_headers(
        parameters: t.Sequence[oas.OASParameter],
        headers_arg: t.Optional[t.Type[t.Any]],
) -> t.Tuple[t.Set[Error], ParamMapping]:
    """Analyzes signature of the handler against the headers.

    axion supports defining headers in signature using:
    - typing_extensions.TypedDict
    - typing.Mapping
    - typing.Dict
    - Any other type is rejected with appropriate error.

    Also, when parsing the signature along with operation, following is taken
    into account:
    1. function does not have "headers" argument and there are no custom OAS headers
        - OK
    2. function does not have "headers" argument and there are custom OAS headers
        - Warning
        - If there are custom headers defined user ought to specify them
          in signature. There was a point to put them inside there after all.
          However they might be used by a middleware or something, not necessarily
          handler. The warning is the only reliable thing to say.
    3. function has "headers" argument and there no custom OAS headers ->
        - OK
        - User might want to get_repr a hold with headers like "Content-Type"
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
    has_param_headers = len(parameters) > 0

    if headers_arg is not None:
        # pre-check type of headers param in signature
        # must be either TypedDict, Mapping or a subclass of those
        is_mapping, is_any = (
            types.is_dict_like(headers_arg),
            types.is_any_type(headers_arg),
        )
        if not (is_mapping or is_any):
            return {
                Error(
                    param_name='headers',
                    reason=IncorrectTypeReason(
                        actual=headers_arg,
                        expected=COOKIES_HEADERS_TYPE,
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
            for rh in oas.OASReservedHeaders
        }
        entries = t.get_type_hints(headers_arg).items()
        if entries:
            for hdr_param_name, hdr_param_type in entries:
                if hdr_param_name not in reserved_headers_keys:
                    logger.opt(record=True).error(
                        '{sig_key} is not one of {reserved_headers} headers',
                        sig_key=hdr_param_name,
                        reserved_headers=oas.OASReservedHeaders,
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
        for hdr in oas.OASReservedHeaders:
            param_mapping[OAS_Param(
                param_in='header',
                param_name=hdr.lower(),
            )] = _get_f_param(hdr)

    return errors, param_mapping


def _analyze_headers_signature_set_oas_set(
        parameters: t.Sequence[oas.OASParameter],
        headers_arg: t.Any,
) -> t.Tuple[t.Set[Error], ParamMapping]:
    logger.opt(record=True).debug('"headers" found both in signature and operation')

    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    param_headers: t.Dict[F_Param,
                          str] = {_get_f_param(rh.name): rh.name
                                  for rh in parameters}
    reserved_headers: t.Dict[F_Param, str] = {
        _get_f_param(rh): rh
        for rh in oas.OASReservedHeaders
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
                        oas_param_type = _build_type_from_oas_param(oas_param)
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


def _analyze_path_query(
        parameters: t.Sequence[oas.OASParameter],
        signature: t.Dict[str, t.Any],
) -> t.Tuple[t.Set[Error], ParamMapping]:
    errors: t.Set[Error] = set()
    param_mapping: t.Dict[OAS_Param, F_Param] = {}

    for op_param in parameters:
        try:
            handler_param_name = _get_f_param(op_param.name)

            handler_param_type = signature.pop(handler_param_name)
            op_param_type = _build_type_from_oas_param(op_param)

            if handler_param_type != op_param_type:
                errors.add(
                    Error(
                        param_name=op_param.name,
                        reason=IncorrectTypeReason(
                            actual=handler_param_type,
                            expected=[op_param_type],
                        ),
                    ),
                )
            else:
                key = OAS_Param(
                    param_in=oas.parameter_in(op_param),
                    param_name=op_param.name,
                )
                param_mapping[key] = handler_param_name
        except KeyError:
            errors.add(
                Error(
                    param_name=op_param.name,
                    reason='missing',
                ),
            )

    return errors, param_mapping


def _build_type_from_oas_param(param: oas.OASParameter) -> t.Any:
    p_type = param.python_type
    p_required = param.required
    if not p_required:
        return t.Optional[p_type]
    else:
        return p_type


@functools.lru_cache(maxsize=100)
def _get_f_param(s: t.Union[str, istr]) -> F_Param:
    return F_Param(CamelCaseToSnakeCaseRegex.sub(r'_\1', s.replace('-', '_')).lower())
