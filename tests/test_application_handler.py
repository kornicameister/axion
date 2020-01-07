import typing as t

from _pytest import logging
import pytest
import typing_extensions as te

from axion import response
from axion.application import handler
from axion.oas import model
from axion.oas import parser
from axion.utils import get_type_repr


def normal_f() -> response.Response:
    ...


async def async_f() -> response.Response:
    ...


@pytest.mark.parametrize(
    'operation_id,error_msg',
    (
        (
            'really_dummy.api.get_all',
            'Failed to import module=really_dummy.api',
        ),
        (
            'tests.test_application_handler.foo',
            'Failed to locate function=foo in module=tests.test_application_handler',
        ),
        (
            'tests.test_application_handler.normal_f',
            'tests.test_application_handler.normal_f did not resolve to coroutine',
        ),
    ),
)
def test_make_handler_bad_cases(
        operation_id: str,
        error_msg: str,
) -> None:
    operation = list(
        parser._resolve_operations(
            components={},
            paths={
                '/{name}': {
                    'post': {
                        'operationId': operation_id,
                        'responses': {
                            'default': {
                                'description': 'fake',
                            },
                        },
                    },
                },
            },
        ),
    )[0]
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler.make(operation)
    assert err.match(error_msg)


def test_resolve_handler_couroutine() -> None:
    assert handler._resolve(
        model.OASOperationId('tests.test_application_handler.async_f'),
    ) is async_f


def test_empty_handler_signature(caplog: logging.LogCaptureFixture) -> None:
    async def foo() -> response.Response:
        ...

    handler._build(
        handler=foo,
        operation=list(
            parser._resolve_operations(
                components={},
                paths={
                    '/{name}': {
                        'post': {
                            'operationId': 'TestAnalysisNoParameters',
                            'responses': {
                                'default': {
                                    'description': 'fake',
                                },
                            },
                        },
                    },
                },
            ),
        )[0],
    )

    assert 'TestAnalysisNoParameters does not declare any parameters' in caplog.messages


def test_not_empty_signature(caplog: logging.LogCaptureFixture) -> None:
    async def foo(
            name: str,
            foo: str,
            bar: str,
            lorem_ipsum: t.List[str],
    ) -> response.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._build(
            handler=foo,
            operation=list(
                parser._resolve_operations(
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
                                'operationId': 'Thor',
                                'responses': {
                                    'default': {
                                        'description': 'fake',
                                    },
                                },
                            },
                        },
                    },
                ),
            )[0],
        )

    assert len(err.value) == 3

    assert err.value['foo'] == 'unexpected'
    assert err.value['bar'] == 'unexpected'
    assert err.value['lorem_ipsum'] == 'unexpected'

    assert (
        'Unconsumed arguments [foo, bar, lorem_ipsum] detected in Thor handler signature'
        in caplog.messages
    )


class TestCookies:
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

    def test_signature_empty_on_oas_cookies(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str) -> response.Response:
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'no_cookies_op', self.operations)),
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
            self,
            the_type: t.Type[t.Any],
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                foo,
                next(filter(lambda op: op.id == 'no_cookies_op', self.operations)),
            )

        assert len(err.value) == 1
        assert 'cookies' in err.value
        assert err.value['cookies'] == 'unexpected'
        assert '"cookies" found in signature but not in operation' in caplog.messages

    def test_signature_empty_oas_cookies(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str) -> response.Response:
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'cookies_op', self.operations)),
        )

        msg = (
            '"cookies" found in operation but not in signature. '
            'Please double check that. axion cannot infer a correctness of '
            'this situations. If you wish to access any "cookies" defined in '
            'specification, they have to be present in your handler '
            'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
            'or typing_extensions.TypedDict[str, typing.Any].'
        )

        assert id(hdrl.fn) == id(foo)
        assert not hdrl.cookie_params
        assert msg in caplog.messages

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
            self,
            the_type: t.Type[t.Any],
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'cookies_op', self.operations)),
        )

        assert id(hdrl.fn) == id(foo)
        assert hdrl.cookie_params

        assert ('csrftoken', 'csrftoken') in hdrl.cookie_params
        assert ('debug', 'debug') in hdrl.cookie_params

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
            self,
            the_type: t.Type[t.Any],
            expected_errors: t.List[t.Tuple[str, str]],
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                foo,
                next(filter(lambda op: op.id == 'cookies_op', self.operations)),
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
            self,
            op_id: str,
            the_type: t.Type[t.Any],
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                foo,
                next(filter(lambda op: op.id == op_id, self.operations)),
            )

        assert len(err.value) == 1
        assert 'cookies' in err.value
        assert err.value['cookies'] == (
            f'expected [typing.Mapping[str, typing.Any],'
            f'typing.Dict[str, typing.Any],typing_extensions.TypedDict]'
            f', but got {utils.get_type_repr(the_type)}'
        )

    @pytest.mark.parametrize(
        'the_type',
        (
            t.Any,
            t.NewType('Cookies', t.Any),  # type: ignore
        ),
    )
    def test_valid_cookies_any_type(
            self,
            the_type: t.Type[t.Any],
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'cookies_op', self.operations)),
        )

        assert id(hdrl.fn) == id(foo)
        assert hdrl.cookie_params
        assert len(hdrl.cookie_params) == 2
        assert ('csrftoken', 'csrftoken') in hdrl.cookie_params
        assert ('debug', 'debug') in hdrl.cookie_params
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
            self,
            the_type: t.Type[t.Any],
            extra_param: str,
    ) -> None:
        async def foo(name: str, cookies: the_type) -> response.Response:  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                foo,
                next(filter(lambda op: op.id == 'cookies_op', self.operations)),
            )

        assert len(err.value) == 1
        assert f'cookies.{extra_param}' in err.value
        assert err.value[f'cookies.{extra_param}'] == 'unknown'


class TestHeaders:
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
                    'operationId': 'no_headers_op',
                    'responses': {
                        'default': {
                            'description': 'fake',
                        },
                    },
                },
                'get': {
                    'operationId': 'headers_op',
                    'responses': {
                        'default': {
                            'description': 'fake',
                        },
                    },
                    'parameters': [
                        {
                            'name': 'X-Trace-Id',
                            'in': 'header',
                            'required': True,
                            'schema': {
                                'type': 'string',
                                'format': 'uuid',
                            },
                        },
                    ],
                },
            },
        },
    )

    @pytest.mark.parametrize(
        'the_type',
        (
            t.Any,
            t.NewType('Headers', t.Any),  # type: ignore
        ),
    )
    @pytest.mark.parametrize('op_id', ('no_headers_op', 'headers_op'))
    def test_valid_headers_any_type(
            self,
            the_type: t.Type[t.Any],
            op_id: str,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, headers: the_type) -> response.Response:  # type: ignore
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == op_id, self.operations)),
        )

        assert id(hdrl.fn) == id(foo)
        assert hdrl.header_params
        msg = (
            'Detected usage of "headers" declared as typing.Any. '
            'axion will allow such declaration but be warned that '
            'you will loose all the help linters (like mypy) offer.'
        )
        assert msg in caplog.messages

    @pytest.mark.parametrize('variation', (0, 1, 2, 3, 4, 5))
    def test_invalid_headers_type(
            self,
            variation: int,
    ) -> None:
        if variation == 0:
            Headers = t.NamedTuple('Headers', [('test', int)])
        elif variation == 1:
            Headers = t.NewType('Headers', list)  # type: ignore
        elif variation == 2:

            class Base(t.NamedTuple):
                test: int

            class Headers(Base):  # type: ignore
                ...
        elif variation == 3:
            Headers = t.NewType('Headers', bool)  # type: ignore
        elif variation == 4:
            Headers = t.AbstractSet[str]  # type: ignore
        else:
            Headers = t.List[str]  # type: ignore

        async def foo(name: str, headers: Headers) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                foo,
                next(filter(lambda op: op.id == 'no_headers_op', self.operations)),
            )

        assert len(err.value) == 1

    def test_oas_headers_signature_empty(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str) -> response.Response:
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'headers_op', self.operations)),
        )

        msg = (
            '"headers" found in operation but not in signature. '
            'Please double check that. axion cannot infer a correctness of '
            'this situations. If you wish to access any "headers" defined in '
            'specification, they have to be present in your handler '
            'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
            'or typing_extensions.TypedDict[str, typing.Any].'
        )

        assert id(hdrl.fn) == id(foo)
        assert not hdrl.header_params
        assert msg in caplog.messages

    def test_no_oas_headers_signature_empty(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str) -> response.Response:
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'no_headers_op', self.operations)),
        )

        assert id(hdrl.fn) == id(foo)
        assert not hdrl.header_params
        assert 'No "headers" in signature and operation parameters' in caplog.messages

    def test_no_oas_headers_mapping(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, headers: t.Mapping[str, str]) -> response.Response:
            ...

        hdrl = handler._build(
            foo,
            next(filter(lambda op: op.id == 'no_headers_op', self.operations)),
        )

        assert id(hdrl.fn) == id(foo)
        assert hdrl.header_params

        assert ('accept', 'accept') in hdrl.header_params
        assert ('authorization', 'authorization') in hdrl.header_params
        assert ('content-type', 'content_type') in hdrl.header_params

        assert '"headers" found in signature but not in operation' in caplog.messages

    def test_no_oas_headers_typed_dict_unknown_header(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class EXTRA_INVALID(te.TypedDict):
            content_length: str

        async def extra_invalid(name: str, headers: EXTRA_INVALID) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                extra_invalid,
                next(filter(lambda op: op.id == 'no_headers_op', self.operations)),
            )

        assert len(err.value) == 1
        assert 'headers.content_length' in err.value
        assert err.value['headers.content_length'] == 'unknown'

    @pytest.mark.parametrize('op_id', ('headers_op', 'no_headers_op'))
    def test_typed_dict_bad_type(
            self,
            op_id: str,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class Invalid(te.TypedDict):
            accept: int

        async def goo(name: str, headers: Invalid) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                goo,
                next(filter(lambda op: op.id == op_id, self.operations)),
            )

        assert len(err.value) == 1
        assert 'headers.accept' in err.value
        assert err.value['headers.accept'] == 'expected [str], but got int'

    def test_no_oas_headers_typed_dict(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class CT(te.TypedDict):
            content_type: str

        class AUTH(te.TypedDict):
            authorization: str

        class ACCEPT(te.TypedDict):
            accept: str

        class FULL(CT, AUTH, ACCEPT):
            ...

        async def content_type(name: str, headers: CT) -> response.Response:
            ...

        async def auth(name: str, headers: AUTH) -> response.Response:
            ...

        async def accept(name: str, headers: ACCEPT) -> response.Response:
            ...

        async def full(name: str, headers: FULL) -> response.Response:
            ...

        for fn in (accept, auth, content_type, full):
            hdrl = handler._build(
                fn,
                next(filter(lambda op: op.id == 'no_headers_op', self.operations)),
            )

            assert id(hdrl.fn) == id(fn)
            assert hdrl.header_params

            if fn is content_type:
                assert ('content-type', 'content_type') in hdrl.header_params

                assert ('accept', 'accept') not in hdrl.header_params
                assert ('authorization', 'authorization') not in hdrl.header_params
            if fn is auth:
                assert ('authorization', 'authorization') in hdrl.header_params

                assert ('accept', 'accept') not in hdrl.header_params
                assert ('content-type', 'content_type') not in hdrl.header_params
            if fn is accept:
                assert ('accept', 'accept') in hdrl.header_params

                assert ('authorization', 'authorization') not in hdrl.header_params
                assert ('content-type', 'content_type') not in hdrl.header_params
            if fn is full:
                assert ('accept', 'accept') in hdrl.header_params
                assert ('authorization', 'authorization') in hdrl.header_params
                assert ('content-type', 'content_type') in hdrl.header_params

            assert '"headers" found in signature but not in operation' in caplog.messages
            caplog.clear()

    def test_oas_headers_signature_mapping(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo(name: str, headers: t.Mapping[str, str]) -> response.Response:
            ...

        operation = next(filter(lambda op: op.id == 'headers_op', self.operations))
        hdrl = handler._build(foo, operation)

        assert id(hdrl.fn) == id(foo)
        assert hdrl.header_params

        assert ('accept', 'accept') in hdrl.header_params
        assert ('authorization', 'authorization') in hdrl.header_params
        assert ('content-type', 'content_type') in hdrl.header_params
        assert ('x-trace-id', 'x_trace_id') in hdrl.header_params
        assert '"headers" found both in signature and operation' in caplog.messages

    def test_oas_headers_signature_typed_dict(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class One(te.TypedDict):
            content_type: str
            x_trace_id: str

        class Two(te.TypedDict):
            authorization: str
            x_trace_id: str

        class Three(te.TypedDict):
            accept: str
            x_trace_id: str

        class FULL(te.TypedDict):
            content_type: str
            accept: str
            authorization: str
            x_trace_id: str

        async def one(name: str, headers: One) -> response.Response:
            ...

        async def two(name: str, headers: Two) -> response.Response:
            ...

        async def three(name: str, headers: Three) -> response.Response:
            ...

        async def full(name: str, headers: FULL) -> response.Response:
            ...

        operation = next(filter(lambda op: op.id == 'headers_op', self.operations))
        for fn in (one, two, three, full):
            hdrl = handler._build(fn, operation)

            assert id(hdrl.fn) == id(fn)
            assert hdrl.header_params

            if fn is one:
                assert ('content-type', 'content_type') in hdrl.header_params
                assert ('x-trace-id', 'x_trace_id') in hdrl.header_params

                assert ('accept', 'accept') not in hdrl.header_params
                assert ('authorization', 'authorization') not in hdrl.header_params
            if fn is two:
                assert ('authorization', 'authorization') in hdrl.header_params
                assert ('x-trace-id', 'x_trace_id') in hdrl.header_params

                assert ('accept', 'accept') not in hdrl.header_params
                assert ('content-type', 'content_type') not in hdrl.header_params
            if fn is three:
                assert ('accept', 'accept') in hdrl.header_params
                assert ('x-trace-id', 'x_trace_id') in hdrl.header_params

                assert ('authorization', 'authorization') not in hdrl.header_params
                assert ('content-type', 'content_type') not in hdrl.header_params
            if fn is full:
                assert ('accept', 'accept') in hdrl.header_params
                assert ('x-trace-id', 'x_trace_id') in hdrl.header_params
                assert ('authorization', 'authorization') in hdrl.header_params
                assert ('content-type', 'content_type') in hdrl.header_params

            assert '"headers" found both in signature and operation' in caplog.messages
            caplog.clear()

    def test_oas_headers_extra_header_typed_dict(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class Invalid(te.TypedDict):
            user_agent: str
            x_trace_id: str

        async def goo(name: str, headers: Invalid) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                goo,
                next(filter(lambda op: op.id == 'headers_op', self.operations)),
            )

        assert len(err.value) == 1
        assert 'headers.user_agent' in err.value
        assert err.value['headers.user_agent'] == 'unknown'

    @pytest.mark.parametrize(
        'the_type',
        (
            int,
            bool,
            float,
            bytes,
            t.Dict[str, str],
            t.AbstractSet[str],
            t.AbstractSet[bool],
            t.Set[int],
            t.Sequence[t.Any],
        ),
    )
    def test_no_oas_headers_typed_dict_bad_type(
            self,
            the_type: t.Type[t.Any],
            caplog: logging.LogCaptureFixture,
    ) -> None:
        class Invalid(te.TypedDict):
            x_trace_id: the_type  # type: ignore

        async def goo(name: str, headers: Invalid) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                goo,
                next(filter(lambda op: op.id == 'headers_op', self.operations)),
            )

        assert len(err.value) == 1
        assert 'headers.x_trace_id' in err.value
        assert (f'expected [str], '
                f'but got {utils.get_type_repr(the_type)}'
                ) == err.value['headers.x_trace_id']


class TestPathQuery:
    operation = list(
        parser._resolve_operations(
            components={},
            paths={
                '/{name}': {
                    'post': {
                        'operationId': 'TestAnalysisParameters',
                        'responses': {
                            'default': {
                                'description': 'fake',
                            },
                        },
                        'parameters': [
                            {
                                'name': 'id',
                                'in': 'path',
                                'required': True,
                                'schema': {
                                    'type': 'string',
                                },
                            },
                            {
                                'name': 'limit',
                                'in': 'query',
                                'schema': {
                                    'type': 'integer',
                                },
                            },
                            {
                                'name': 'page',
                                'in': 'query',
                                'schema': {
                                    'type': 'number',
                                },
                            },
                            {
                                'name': 'includeExtra',
                                'in': 'query',
                                'schema': {
                                    'type': 'boolean',
                                    'default': True,
                                },
                            },
                        ],
                    },
                },
            },
        ),
    )[0]

    def test_signature_mismatch_missing(self) -> None:
        async def foo(
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'TestAnalysisParameters'
        assert len(err.value) == 1
        assert 'id' in err.value
        assert err.value['id'] == 'missing'

    def test_signature_all_missing(self) -> None:
        async def foo() -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'TestAnalysisParameters'
        assert len(err.value) == 4
        for key in ('id', 'limit', 'page', 'includeExtra'):
            assert key in err.value
            assert err.value[key] == 'missing'

    def test_signature_mismatch_bad_type(self) -> None:
        async def foo(
                id: bool,
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'TestAnalysisParameters'
        assert len(err.value) == 1
        assert 'id' in err.value
        assert err.value['id'] == 'expected [str], but got bool'

    def test_signature_all_bad_type(self) -> None:
        async def foo(
                id: float,
                limit: t.Optional[t.Union[int, float]],
                page: t.Optional[t.AbstractSet[bool]],
                include_extra: t.Union[int, str],
        ) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'TestAnalysisParameters'
        assert len(err.value) == 4
        for mismatch in err.value:
            actual_msg = err.value[mismatch.param_name]
            expected_msg = None

            if mismatch.param_name == 'id':
                expected_msg = 'expected [str], but got float'
            elif mismatch.param_name == 'limit':
                expected_msg = (
                    'expected [typing.Optional[int]], but got '
                    'typing.Optional[typing.Union[float, int]]'
                )
            elif mismatch.param_name == 'page':
                expected_msg = (
                    'expected [typing.Optional[float]], but got '
                    'typing.Optional[typing.AbstractSet[bool]]'
                )
            elif mismatch.param_name == 'includeExtra':
                expected_msg = (
                    'expected [typing.Optional[bool]], but got '
                    'typing.Union[int, str]'
                )

            assert expected_msg is not None
            assert actual_msg == expected_msg

    def test_signature_match(self) -> None:
        async def test_handler(
                id: str,
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> response.Response:
            ...

        hdrl = handler._build(
            handler=test_handler,
            operation=self.operation,
        )

        assert len(hdrl.path_params) == 1
        assert len(hdrl.query_params) == 3


class TestBody:
    def test_no_request_body_empty_signature(self) -> None:
        async def test() -> response.Response:
            ...

        hdrl = handler._build(
            handler=test,
            operation=TestBody._make_operation(None),
        )

        assert not hdrl.has_body

    @pytest.mark.parametrize('required', (True, False))
    def test_request_body_signature_set(self, required: bool) -> None:
        async def test(body: t.Dict[str, t.Any]) -> response.Response:
            ...

        hdrl = handler._build(
            handler=test,
            operation=TestBody._make_operation({
                'requestBody': {
                    'required': required,
                    'content': {
                        'text/plain': {
                            'schema': {
                                'type': 'string',
                            },
                        },
                    },
                },
            }),
        )

        assert hdrl.has_body

    def test_request_body_required_signature_optional(self) -> None:
        async def test(body: t.Optional[t.Dict[str, t.Any]]) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestBody._make_operation({
                    'requestBody': {
                        'required': True,
                        'content': {
                            'text/plain': {
                                'schema': {
                                    'type': 'string',
                                },
                            },
                        },
                    },
                }),
            )

        assert err.value
        assert 1 == len(err.value)
        assert 'body' in err.value
        assert err.value['body'] == (
            'expected '
            '[typing.Mapping[str, typing.Any],typing.Dict[str, typing.Any]]'
            ', but got '
            'typing.Optional[typing.Dict[str, typing.Any]]'
        )

    @pytest.mark.parametrize(
        'the_type',
        (
            t.Dict[str, t.Any],
            t.Mapping[str, t.Any],
            t.NewType('Body', t.Dict[str, t.Any]),
            t.NewType('Body', t.Dict[str, str]),
            t.NewType('Body', t.Mapping[str, t.Any]),  # type: ignore
            t.NewType('Body', t.Mapping[str, str]),  # type: ignore
        ),
    )
    def test_request_body_different_types(
            self,
            the_type: t.Any,
    ) -> None:
        async def test(body: the_type) -> response.Response:  # type: ignore
            ...

        hdrl = handler._build(
            handler=test,
            operation=TestBody._make_operation({
                'requestBody': {
                    'required': True,
                    'content': {
                        'text/plain': {
                            'schema': {
                                'type': 'string',
                            },
                        },
                    },
                },
            }),
        )

        assert hdrl.has_body

    def test_no_request_body_signature_set(
            self,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def test(body: t.Dict[str, t.Any]) -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestBody._make_operation(None),
            )

        assert err.value
        assert 1 == len(err.value)
        assert 'body' in err.value
        assert 'unexpected' == err.value['body']

        assert (
            'Operation does not define a request body, but it is '
            'specified in handler signature.'
        ) in caplog.messages

    @pytest.mark.parametrize('required', (True, False))
    def test_request_body_empty_signature(
            self,
            required: bool,
            caplog: logging.LogCaptureFixture,
    ) -> None:
        async def foo() -> response.Response:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=foo,
                operation=TestBody._make_operation({
                    'requestBody': {
                        'required': required,
                        'content': {
                            'text/plain': {
                                'schema': {
                                    'type': 'string',
                                },
                            },
                        },
                    },
                }),
            )

        assert err.value
        assert 1 == len(err.value)
        assert 'body' in err.value
        assert 'missing' == err.value['body']

        assert (
            'Operation defines a request body, but it is not specified in '
            'handler signature'
        ) in caplog.messages

    @staticmethod
    def _make_operation(
        request_body_def: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> model.OASOperation:
        return list(
            parser._resolve_operations(
                components={},
                paths={
                    '/one': {
                        'post': {
                            **(request_body_def or {}),
                            **{
                                'operationId': 'empty_response_body',
                                'responses': {
                                    '204': {
                                        'description': 'fake',
                                    },
                                },
                            },
                        },
                    },
                },
            ),
        )[0]


class TestReturnType:
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
                    'ResponsePartial_DifferentTypes_V1',
                    {
                        'http_code': int,
                        'links': t.List[str],
                    },
                ),
                te.TypedDict(  # type: ignore
                    'ResponsePartial_DifferentTypes_V2',
                    {
                        'http_code': int,
                        'headers': t.Mapping[str, str],
                        'links': t.List[str],
                    },
                ),
                te.TypedDict(   # type: ignore
                    'ResponsePartial_DifferentTypes_V3',
                    {
                        'http_code': int,
                        'headers': t.Mapping[str, str],
                        'cookies': t.Mapping[str, str],
                        'links': t.List[str],
                    },
                ),
                te.TypedDict(  # type: ignore
                    'ResponsePartial_DifferentTypes_V4',
                    {
                        'http_code': int,
                        'body': t.List[t.Dict[str, t.Any]],
                        'headers': t.Mapping[str, str],
                        'cookies': t.Mapping[str, str],
                        'links': t.List[str],
                    },
                ),
            )
        ),
    )
    def test_correct_handler(
            self,
            response_code: t.Union[str, int],
            return_type: t.Type[t.Any],
    ) -> None:
        async def test() -> return_type:  # type: ignore
            ...

        handler._build(
            handler=test,
            operation=TestReturnType._make_operation({
                'f{response_code}': {
                    'description': f'Returning {return_type}',
                },
            }),
        )

    @pytest.mark.parametrize(
        'return_codes,unaccounted_response_codes',
        (
            ((200, 201), (204, 202)),
            ((201, 204), (200, 500)),
            ((200, 201, 300, 301), (500, 503)),
        ),
    )
    def test_handler_http_code_literal_unaccounted(
            self,
            return_codes: t.Sequence[int],
            unaccounted_response_codes: t.Sequence[int],
    ) -> None:
        test_returns = te.TypedDict(  # type: ignore
            'NoMatch',
            {'http_code': te.Literal[return_codes]},  # type: ignore
        )

        async def test() -> test_returns:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
                    **{
                        f'{rc}': {
                            'description': f'Matching code {rc}',
                        }
                        for rc in return_codes
                    },
                    **{
                        f'{rc}': {
                            'description': f'Returning {rc} but '
                            f'handler has {return_codes} :D',
                        }
                        for rc in unaccounted_response_codes
                    },
                }),
            )

        assert err
        assert err.value
        assert len(unaccounted_response_codes) == len(err.value)
        for rc in unaccounted_response_codes:
            assert f'return.http_code[{rc}]' in err.value
            assert 'missing' == err.value[f'return.http_code[{rc}]']

    @pytest.mark.parametrize(
        'return_codes,extra_codes',
        (
            ((200, 201, 202), (204, )),
            ((200, 201, 500), (303, )),
            ((500, 503), (204, )),
            ((201, 204, 404, 500), (401, )),
            ((200, ), (204, 300, 500)),
            ((200, 204), (300, 500)),
        ),
    )
    def test_handler_http_code_literal_extra_codes(
            self,
            return_codes: t.Sequence[int],
            extra_codes: t.Sequence[int],
    ) -> None:
        rt_codes = list(return_codes)
        rt_codes.extend(extra_codes)

        test_returns = te.TypedDict(
            'NoMatch',
            {'http_code': te.Literal[tuple(rt_codes)]},  # type: ignore
        )

        async def test() -> test_returns:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
                    **{
                        f'{rc}': {
                            'description': f'Returning {rc}',
                        }
                        for rc in return_codes
                    },
                }),
            )

        assert err
        assert err.value
        assert len(extra_codes) == len(err.value)
        for rc in extra_codes:
            assert f'return.http_code[{rc}]' in err.value
            assert 'unexpected' == err.value[f'return.http_code[{rc}]']

    def test_return_type_literal_with_default_entry(self) -> None:
        async def test() -> te.TypedDict(  # type: ignore
                'R',
                http_code=te.Literal[204, 'default'],
        ):
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
                    '204': {
                        'description': '1',
                    },
                    'default': {
                        'description': '2',
                    },
                }),
            )

        assert err
        assert err.value
        assert 1 == len(err.value)
        assert 'return.http_code[default]' in err.value
        assert 'unexpected' == err.value['return.http_code[default]']

    def test_missing_return_annotation(self) -> None:
        async def test():  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
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
            self,
            response_code: t.Union[str, te.Literal['default']],
    ) -> None:
        test_returns = te.TypedDict(  # type: ignore
            'MissingHttpCode',
            {'body': t.Dict[str, int]},
        )

        async def test() -> test_returns:
            ...

        handler._build(
            handler=test,
            operation=TestReturnType._make_operation({
                f'{response_code}': {
                    'description': 'I am alone',
                },
            }),
        )

    def test_omitted_return_code_couple_oas_resp(self) -> None:
        test_returns = te.TypedDict(  # type: ignore
            'MissingHttpCode',
            {'body': t.Dict[str, int]},
        )

        async def test() -> test_returns:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
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
            t.Mapping[str, str],
            t.Dict[str, str],
            None,
        ),
    )
    def test_incorrect_return_type(self, return_type: t.Type[t.Any]) -> None:
        async def test() -> return_type:  # type: ignore
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._build(
                handler=test,
                operation=TestReturnType._make_operation({
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
            f'expected [Response{{body: typing.Any, headers: typing.Mapping[str, str], '
            f'cookies: typing.Mapping[str, str]}}], but got '
            f'{utils.get_type_repr(return_type if return_type else type(None))}'
        ) == err.value['return']

    @staticmethod
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
