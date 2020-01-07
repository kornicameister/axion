import asyncio
from dataclasses import dataclass
import functools
import importlib
import re
import sys
import typing as t

from loguru import logger
from multidict import istr
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

BODY_EXPECTED_TYPES = [
    t.Mapping[str, t.Any],
    t.Dict[str, t.Any],
]

AXION_RESPONSE_ENTRIES = getattr(response.Response, '__annotations__', {})
AXION_RESPONSE_KEYS = frozenset(AXION_RESPONSE_ENTRIES.keys())

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


Reason = t.Union[te.Literal['missing', 'unexpected', 'unknown'], IncorrectTypeReason]


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
        rt_entries = getattr(return_type, '__annotations__', {})

        if AXION_RESPONSE_KEYS.intersection(set(rt_entries.keys())):
            # TODO(kornicameister) analyze other entries,
            # like maybe body or headers/cookies?
            return _analyze_return_type_http_code(
                operation,
                rt_entries.pop('http_code', None),
            )
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


def _analyze_return_type_http_code(
        operation: oas.OASOperation,
        rt_http_code: t.Optional[t.Any],
) -> t.Set[Error]:
    if rt_http_code is None:
        # if there's no http_code in return Response
        # this is permitted only if there's single response defined in
        # OAS responses

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
            return {
                Error(
                    param_name='return.http_code',
                    reason='missing',
                ),
            }
        else:
            logger.opt(
                lazy=True,
                record=True,
            ).debug(
                'Operation {id} handler skips return.http_code',
                id=lambda: operation.id,
            )
            return set()
    elif ti.is_literal_type(rt_http_code):
        errors: t.Set[Error] = set()
        rt_literal_args = frozenset(ti.get_args(rt_http_code, utils.IS_NEW_TYPING))
        responses_codes = frozenset(operation.responses.keys())

        assert responses_codes, 'there should be response codes in this place'
        assert rt_literal_args, 'literal should have entries'

        has_default_rt_code = 'default' in rt_literal_args
        if has_default_rt_code:
            logger.opt(
                lazy=True,
                record=True,
            ).error(
                'Operation {id} handler has return.http_code defined as {literal}. '
                'One of the entries is "default". This is invalid because HTTP '
                'response code must be `int`. Having "default" OAS response '
                'means being able to return any `int` from [200, ...] range '
                'that will match "default" OAS response.',
                id=lambda: operation.id,
                literal=lambda: repr(te.Literal),
            )
            errors.add(
                Error(
                    param_name='return.http_code[default]',
                    reason='unexpected',
                ),
            )
        elif len(responses_codes) == 1 and 'default' in responses_codes:
            # if user is not tempted to return `default` as http_code and
            # in the same time OAS has just one response and that response is
            # `default` all that needs to be checked is if `rt_literal_args`
            # are all subclasse of `int`,`float`
            # TODO(kornicameister) think about it !
            return errors

        missing_rt_codes = responses_codes.difference(rt_literal_args)
        extra_codes = frozenset(rt_literal_args - responses_codes)

        if missing_rt_codes:
            # case where OAS defines code like 200,201,203,default
            # but Literal defines just 200 which makes 201,203 missing
            # axion's idea is to aid with OAS services development by ensuring
            # that implementation matches the specification. If specification
            # says that 4 codes ought are possible and user defines http_code
            # as Literal, it is better to make this reminder to him. Either
            # codes ought to be accounted for or some of them are actually
            # invalid
            logger.opt(
                lazy=True,
                record=True,
            ).error(
                'Operation {id} handler has return.http_code defined as {literal} '
                'but http codes in it do not match http codes in OAS operation. '
                'Following codes are not accounted for [{missing_rt_codes}]',
                id=lambda: operation.id,
                literal=lambda: repr(te.Literal),
                missing_rt_codes=lambda: ','.join(map(str, missing_rt_codes)),
            )
            errors.update(
                Error(
                    param_name=f'return.http_code[{mc}]',
                    reason='missing',
                ) for mc in missing_rt_codes
            )

        if extra_codes:
            # this has similar message as above. Imagine that your operation
            # has respones likes 204, 404, 500 but your handler actually says
            # that it is doable to return 301. Well welcome to kindgom of
            # Literal. This is again for two-time checking of own back. axion
            # is strict as much as it can but it does to prevent accidents from
            # happening.
            logger.opt(
                lazy=True,
                record=True,
            ).error(
                'Operation {id} handler has return.http_code defined as {literal}. '
                'Following codes are not part [{extra_codes}] are not defined '
                'in operation response codes. ',
                id=lambda: operation.id,
                literal=lambda: repr(te.Literal),
                extra_codes=lambda: ','.join(map(str, extra_codes)),
            )
            errors.update(
                Error(
                    param_name=f'return.http_code[{mc}]',
                    reason='unexpected',
                ) for mc in extra_codes
            )

        return errors
    elif utils.is_new_type(rt_http_code):
        logger.opt(
            lazy=True,
            record=True,
        ).debug(
            'Operation {id} handler defines return.http_code as typing.NewType',
            id=lambda: operation.id,
        )
        return _analyze_return_type_http_code(operation, rt_http_code.__supertype__)
    elif issubclass(rt_http_code, (int, float)):
        logger.opt(
            lazy=True,
            record=True,
        ).debug(
            'Operation {id} handler defines return.http_code as "int" or "float"',
            id=lambda: operation.id,
        )
        return set()
    else:
        return {
            Error(
                param_name='return.http_code',
                reason=IncorrectTypeReason(
                    actual=rt_http_code,
                    expected=[
                        int,
                        float,
                        t.NewType('HttpCode', int),
                        t.NewType('HttpCode', float),
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
                    expected=BODY_EXPECTED_TYPES,
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
