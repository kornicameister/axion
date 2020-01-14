import typing as t

import pytest
import typing_extensions as te

from axion import handler
from axion import response
from axion.oas import model
from axion.oas import parser
from axion.utils import get_type_repr


@pytest.mark.parametrize(
    'response_code,return_type',
    (
        (
            response_code,
            return_type,
        ) for response_code in [
            200,
            201,
            204,
            300,
            401,
            404,
            500,
            503,
        ] for return_type in (
            response.Response,
            te.TypedDict(  # type: ignore
                'JustHttpCodeIsOk',
                {'http_code': int},
            ),
            te.TypedDict(  # type: ignore
                'JustHttpCodeIsAsNewType_Int',
                {'http_code': t.NewType('HTTP_CODE', int)},
            ),
            te.TypedDict(  # type: ignore
                'HttpCodeWithSomeJunkThatWillBeIgnored',
                {
                    'http_code': int,
                    'foo': str,
                    'bar': bool,
                },
            ),
            te.TypedDict(  # type: ignore
                f'HttpCodeDefinedAs_Literal[{response_code}]',
                {'http_code': te.Literal[response_code]},
            ),
            te.TypedDict(  # type: ignore
                f'HttpCodeDefinedAs_Literal_&_NewType[{response_code}]',
                {'http_code': t.NewType('HttpCode', te.Literal[response_code])},
            ),
            te.TypedDict(  # type: ignore
                'Response_V1',
                {
                    'http_code': int,
                    'links': t.List[str],
                },
            ),
            te.TypedDict(  # type: ignore
                'Response_V2',
                {
                    'http_code': int,
                    'headers': t.Mapping[str, str],
                    'links': t.List[str],
                },
            ),
            te.TypedDict(   # type: ignore
                'Response_V3',
                {
                    'http_code': int,
                    'headers': t.Mapping[str, str],
                    'cookies': t.Mapping[str, str],
                    'links': t.List[str],
                },
            ),
            te.TypedDict(  # type: ignore
                'Response_V4',
                {
                    'http_code': int,
                    'body': te.Literal[None],
                    'headers': t.Mapping[str, str],
                    'cookies': t.Mapping[str, str],
                    'links': t.List[str],
                },
            ),
            te.TypedDict(  # type: ignore
                'Response_V5',
                http_code=int,
                body=None,
            ),
        )
    ),
)
def test_correct_handler_no_oas_body(
        response_code: int,
        return_type: t.Type[t.Any],
) -> None:
    async def test() -> return_type:  # type: ignore
        ...

    operation = _make_operation({
        f'{response_code}': {
            'description': f'Returning {return_type}',
        },
    })
    handler._resolve(
        handler=test,
        operation=operation,
    )


def test_missing_return_annotation() -> None:
    async def test():  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '204': {
                    'description': 'It will not work anyway',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)
    assert 'return' in err.value
    assert 'missing' == err.value['return']


@pytest.mark.parametrize('response_code', (200, 300, 400, 'default'))
def test_omitted_return_code_single_oas_resp(
        response_code: t.Union[str, te.Literal['default']],
) -> None:
    test_returns = te.TypedDict(  # type: ignore
        'MissingHttpCode',
        {'body': t.Dict[str, int]},
    )

    async def test() -> test_returns:
        ...

    handler._resolve(
        handler=test,
        operation=_make_operation({
            f'{response_code}': {
                'description': 'I am alone',
            },
        }),
    )


def test_omitted_return_code_couple_oas_resp() -> None:
    test_returns = te.TypedDict(  # type: ignore
        'MissingHttpCode',
        {'body': t.Dict[str, int]},
    )

    async def test() -> test_returns:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '200': {
                    'description': 'I am alone',
                },
                '300': {
                    'description': 'I am alone',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)
    assert 'return.http_code' in err.value
    assert 'missing' == err.value['return.http_code']


@pytest.mark.parametrize(
    'return_type',
    (
        int,
        float,
        None,
        t.Mapping[str, str],
        t.Dict[str, str],
    ),
)
def test_incorrect_return_type(return_type: t.Type[t.Any]) -> None:
    async def test() -> return_type:  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '204': {
                    'description': 'Incorrect return type',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)
    assert 'return' in err.value

    assert (
        f'expected [{get_type_repr.get_repr(response.Response)}], but got '
        f'{get_type_repr.get_repr(return_type if return_type else type(None))}'
    ) == err.value['return']


@pytest.mark.parametrize(
    'headers_type',
    (
        int,
        float,
        complex,
        t.List[str],
        t.Set[t.Tuple[str, str]],
    ),
)
def test_incorrect_headers_type(headers_type: t.Type[t.Any]) -> None:
    test_returns = te.TypedDict(  # type: ignore
        'RV_Bad_Headers',
        {'http_code': int, 'headers': headers_type},  # type: ignore
    )

    async def test() -> test_returns:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '204': {
                    'description': 'Incorrect return type',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)
    assert 'return.headers' in err.value

    assert (
        f'expected ['
        f'typing.Mapping[str, typing.Any],'
        f'typing.Dict[str, typing.Any],'
        f'typing_extensions.TypedDict], '
        f'but got '
        f'{get_type_repr.get_repr(headers_type)}'
    ) == err.value['return.headers']


@pytest.mark.parametrize(
    'cookies_type',
    (
        int,
        float,
        complex,
        t.List[str],
        t.Set[t.Tuple[str, str]],
    ),
)
def test_incorrect_cookies_type(cookies_type: t.Type[t.Any]) -> None:
    test_returns = te.TypedDict(  # type: ignore
        'RV_Bad_Cookies',
        {'http_code': int, 'cookies': cookies_type},  # type: ignore
    )

    async def test() -> test_returns:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '204': {
                    'description': 'Incorrect return type',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)
    assert 'return.cookies' in err.value

    assert (
        f'expected ['
        f'typing.Mapping[str, typing.Any],'
        f'typing.Dict[str, typing.Any],'
        f'typing_extensions.TypedDict], '
        f'but got '
        f'{get_type_repr.get_repr(cookies_type)}'
    ) == err.value['return.cookies']


@pytest.mark.parametrize(
    'return_code',
    (
        str,
        bool,
        t.NewType('HttpCode', bool),
        t.NewType('HTTP_CODE', float),
        te.Literal['c', 'o', 'd', 'e'],
        te.Literal[13.0],
    ),
)
def test_incorrect_return_http_code(return_code: t.Type[t.Any]) -> None:
    test_returns = te.TypedDict(  # type: ignore
        f'ReturnWithCodeAs_{return_code}',
        {'http_code': return_code},
    )

    async def test() -> test_returns:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
                '204': {
                    'description': 'Incorrect return type',
                },
            }),
        )

    assert err
    assert err.value
    assert 1 == len(err.value)


def _make_operation(responses_def: t.Dict[str, t.Any]) -> model.OASOperation:
    return list(
        parser._resolve_operations(
            components={},
            paths={
                '/testReturnType': {
                    'get': {
                        'operationId': 'empty_response_body',
                        'responses': responses_def,
                    },
                },
            },
        ),
    )[0]
