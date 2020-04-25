import typing as t

from _pytest import logging
import pytest
import typing_extensions as te

from axion import handler
from axion import response
from axion.oas import parser
from axion.utils import get_type_repr

operations = parser._resolve_operations(
    components={},
    paths={
        '/{name}': {
            'parameters': [
                {
                    'name': 'name',
                    'in': 'path',
                    'required': True,
                    'schema': {
                        'type': 'string',
                    },
                },
            ],
            'post': {
                'operationId': 'no_cookies_op',
                'responses': {
                    'default': {
                        'description': 'fake',
                    },
                },
            },
            'get': {
                'operationId': 'cookies_op',
                'responses': {
                    'default': {
                        'description': 'fake',
                    },
                },
                'parameters': [
                    {
                        'in': 'cookie',
                        'name': 'csrftoken',
                        'required': True,
                        'schema': {
                            'type': 'string',
                        },
                    },
                    {
                        'in': 'cookie',
                        'name': 'debug',
                        'required': True,
                        'schema': {
                            'type': 'boolean',
                        },
                    },
                ],
            },
        },
    },
)


def test_signature_empty_no_oas_cookies(caplog: logging.LogCaptureFixture) -> None:
    async def foo(name: str) -> response.Response:
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'no_cookies_op', operations)),
    )

    assert id(hdrl.fn) == id(foo)
    assert not hdrl.cookie_params
    assert 'No "cookies" in signature and operation parameters' in caplog.messages


@pytest.mark.parametrize(
    'the_type',
    (
        t.Mapping[str, str],
        t.Dict[str, str],
        te.TypedDict(  # type: ignore
            'Cookies', {
                'debug': bool,
                'csrftoken': str,
            },
        ),
    ),
)
def test_signature_set_no_oas_cookies(
    the_type: t.Type[t.Any],
    caplog: logging.LogCaptureFixture,
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            foo,
            next(filter(lambda op: op.id == 'no_cookies_op', operations)),
        )

    assert len(err.value) == 1
    assert 'cookies' in err.value
    assert err.value['cookies'] == 'unexpected'
    assert '"cookies" found in signature but not in operation' in caplog.messages


def test_signature_empty_oas_cookies(caplog: logging.LogCaptureFixture) -> None:
    async def foo(name: str) -> response.Response:
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'cookies_op', operations)),
    )

    msg = (
        '"cookies" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "cookies" defined in '
        'specification, they have to be present in your handler '
        'as '
    )

    assert id(hdrl.fn) == id(foo)
    assert not hdrl.cookie_params
    assert any(filter(lambda m: t.cast(str, m).startswith(msg), caplog.messages))


@pytest.mark.parametrize(
    'the_type',
    (
        t.Mapping[str, str],
        t.Dict[str, str],
        te.TypedDict(  # type: ignore
            'Cookies', {
                'debug': bool,
                'csrftoken': str,
            },
        ),
    ),
)
def test_signature_set_oas_cookies(
    the_type: t.Type[t.Any],
    caplog: logging.LogCaptureFixture,
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'cookies_op', operations)),
    )

    assert id(hdrl.fn) == id(foo)
    assert hdrl.cookie_params

    assert ('csrftoken', 'csrftoken') in hdrl.cookie_params.items()
    assert ('debug', 'debug') in hdrl.cookie_params.items()

    assert '"cookies" found both in signature and operation' in caplog.messages


@pytest.mark.parametrize(
    'the_type,expected_errors',
    (
        (
            te.TypedDict('Cookies', csrftoken=bool, debug=bool),  # type: ignore
            [
                (
                    'csrftoken',
                    'expected [str], but got bool',
                ),
            ],
        ),
        (
            te.TypedDict('Cookies', csrftoken=str, debug=int),  # type: ignore
            [
                (
                    'debug',
                    'expected [bool], but got int',
                ),
            ],
        ),
        (
            te.TypedDict(  # type: ignore
                'Cookies',
                csrftoken=t.List[str],
                debug=t.List[int],
            ),
            [
                (
                    'debug',
                    'expected [bool], but got typing.List[int]',
                ),
                (
                    'csrftoken',
                    'expected [str], but got typing.List[str]',
                ),
            ],
        ),
    ),
)
def test_signature_set_bad_oas_cookies_type_mismatch(
    the_type: t.Type[t.Any],
    expected_errors: t.List[t.Tuple[str, str]],
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            foo,
            next(filter(lambda op: op.id == 'cookies_op', operations)),
        )

    assert len(err.value) == len(expected_errors)
    for param_key, error_msg in expected_errors:
        assert f'cookies.{param_key}' in err.value
        assert err.value[f'cookies.{param_key}'] == error_msg


@pytest.mark.parametrize(
    'the_type',
    (
        t.NamedTuple('Cookies', [('csrftoken', str), ('debug', bool)]),
        int,
        bool,
        t.NewType('Cookies', int),
        t.NewType('Cookies', bool),
        t.List[str],
        t.AbstractSet[str],
        t.Set[str],
    ),
)
@pytest.mark.parametrize('op_id', ('no_cookies_op', 'cookies_op'))
def test_invalid_cookies_type(
    op_id: str,
    the_type: t.Type[t.Any],
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            foo,
            next(filter(lambda op: op.id == op_id, operations)),
        )

    assert len(err.value) == 1
    assert 'cookies' in err.value
    assert err.value['cookies'] == (
        f'expected [typing.Mapping[str, typing.Any],'
        f'typing.Dict[str, typing.Any],typing_extensions.TypedDict]'
        f', but got {get_type_repr.get_repr(the_type)}'
    )


@pytest.mark.parametrize(
    'the_type',
    (
        t.Any,
        t.NewType('Cookies', t.Any),  # type: ignore
    ),
)
def test_valid_cookies_any_type(
    the_type: t.Type[t.Any],
    caplog: logging.LogCaptureFixture,
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'cookies_op', operations)),
    )

    assert id(hdrl.fn) == id(foo)
    assert hdrl.cookie_params
    assert len(hdrl.cookie_params) == 2
    assert ('csrftoken', 'csrftoken') in hdrl.cookie_params.items()
    assert ('debug', 'debug') in hdrl.cookie_params.items()
    msg = (
        'Detected usage of "cookies" declared as typing.Any. '
        'axion will allow such declaration but be warned that '
        'you will loose all the help linters (like mypy) offer.'
    )
    assert msg in caplog.messages


@pytest.mark.parametrize(
    'the_type,extra_param',
    (
        (te.TypedDict(  # type: ignore
            'Cookies', {
                'debug': bool,
                'csrftoken': str,
                'foo': int,
            },
        ), 'foo'),
        (te.TypedDict(  # type: ignore
            'Cookies', {
                'debug': bool,
                'csrftoken': str,
                'bar': int,
            },
        ), 'bar'),
    ),
)
def test_signature_set_bad_oas_cookies_unknown(
    the_type: t.Type[t.Any],
    extra_param: str,
) -> None:
    async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            foo,
            next(filter(lambda op: op.id == 'cookies_op', operations)),
        )

    assert len(err.value) == 1
    assert f'cookies.{extra_param}' in err.value
    assert err.value[f'cookies.{extra_param}'] == 'unknown'
