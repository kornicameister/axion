import typing as t

from loguru import logger
import typing_extensions as te
import typing_inspect as ti

from axion import oas
from axion import pipeline
from axion.handler import exceptions
from axion.handler import model
from axion.utils import types


def analyze(
    operation: oas.OASOperation,
    signature: t.Dict[str, t.Any],
) -> t.Set[exceptions.Error]:
    if 'return' not in signature:
        logger.error(
            'Operation {id} handler does not define return annotation',
            id=operation.id,
        )
        return {exceptions.Error(param_name='return', reason='missing')}
    else:
        return_type = signature.pop('return')
        rt_entries = getattr(return_type, '__annotations__', {}).copy()
        matching_keys = model.AXION_RESPONSE_KEYS.intersection(set(rt_entries.keys()))

        logger.opt(lazy=True).debug(
            'Operation {id} handler defines [{keys}] in return type',
            id=lambda: operation.id,
            keys=lambda: ','.join(rt_entries.keys()),
        )

        if matching_keys:
            return {
                *_analyze_http_code(
                    operation,
                    rt_entries.pop('http_code', None),
                ),
                *_analyze_cookies(
                    operation,
                    rt_entries.pop('cookies', None),
                ),
                *_analyze_headers(
                    operation,
                    rt_entries.pop('headers', None),
                ),
            }
        else:
            logger.opt(lazy=True).error(
                'Operation {id} handler return type is incorrect, '
                'expected {expected_type} but received {actual_type}',
                id=lambda: operation.id,
                expected_type=lambda: pipeline.Response,
                actual_type=lambda: return_type,
            )
            return {
                exceptions.Error(
                    param_name='return',
                    reason=exceptions.IncorrectTypeReason(
                        expected=[pipeline.Response],
                        actual=return_type,
                    ),
                ),
            }


def _analyze_headers(
    operation: oas.OASOperation,
    headers: t.Optional[t.Type[t.Any]],
) -> t.Set[exceptions.Error]:
    if headers is not None:
        if types.is_any_type(headers):
            logger.warning(
                'Detected usage of "return.headers" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
            return set()
        elif not types.is_dict_like(headers):
            return {
                exceptions.Error(
                    param_name='return.headers',
                    reason=exceptions.IncorrectTypeReason(
                        expected=model.COOKIES_HEADERS_TYPE,
                        actual=headers,
                    ),
                ),
            }
    return set()


def _analyze_cookies(
    operation: oas.OASOperation,
    cookies: t.Optional[t.Type[t.Any]],
) -> t.Set[exceptions.Error]:
    if cookies is not None:
        if types.is_any_type(cookies):
            logger.warning(
                'Detected usage of "return.cookies" declared as typing.Any. '
                'axion will allow such declaration but be warned that '
                'you will loose all the help linters (like mypy) offer.',
            )
            return set()
        elif not types.is_dict_like(cookies):
            return {
                exceptions.Error(
                    param_name='return.cookies',
                    reason=exceptions.IncorrectTypeReason(
                        expected=model.COOKIES_HEADERS_TYPE,
                        actual=cookies,
                    ),
                ),
            }
    return set()


def _analyze_http_code(
    operation: oas.OASOperation,
    rt_http_code: t.Optional[t.Type[t.Any]],
) -> t.Set[exceptions.Error]:

    if rt_http_code is None:
        # if there's no http_code in return Response
        # this is permitted only if there's single response defined in
        # OAS responses. User needs to set it otherwise how can we tell if
        # everything is correct
        if len(operation.responses) != 1:
            logger.opt(lazy=True).error(
                'Operation {id} handler skips return.http_code but it is impossible '
                ' with {count_of_ops} responses due to ambiguity.',
                id=lambda: operation.id,
                count_of_ops=lambda: len(operation.responses),
            )
            return {exceptions.Error(
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
        if not all(issubclass(lmt, model.HTTP_CODE_TYPE) for lmt in literal_types):
            return {
                exceptions.Error(
                    param_name='return.http_code',
                    reason=exceptions.CustomReason(f'expected {repr(te.Literal)}[int]'),
                ),
            }
        return set()

    elif ti.is_new_type(rt_http_code):
        # not quite sure why user would like to alias that
        # but it is not a problem for axion as long `NewType` embedded type
        # is fine
        return _analyze_http_code(operation, rt_http_code.__supertype__)

    elif issubclass(rt_http_code, bool):
        # yeah, Python rocks -> bool is subclass of an int
        # not quite sure wh that happens, perhaps someone sometime
        # will answer that question
        return {
            exceptions.Error(
                param_name='return.http_code',
                reason=exceptions.IncorrectTypeReason(
                    expected=[model.HTTP_CODE_TYPE],
                    actual=bool,
                ),
            ),
        }
    else:

        try:
            assert issubclass(rt_http_code, model.HTTP_CODE_TYPE)
            return set()
        except (AssertionError, TypeError):
            ...
        return {
            exceptions.Error(
                param_name='return.http_code',
                reason=exceptions.IncorrectTypeReason(
                    actual=rt_http_code,
                    expected=[
                        type(None),
                        model.HTTP_CODE_TYPE,
                        t.NewType('HttpCode', model.HTTP_CODE_TYPE),
                        te.Literal,
                    ],
                ),
            ),
        }
