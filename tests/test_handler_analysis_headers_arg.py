import typing as t

from _pytest import logging
import pytest
import pytest_mock as ptm
import typing_extensions as te

from axion import handler
from axion import pipeline
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
    the_type: t.Type[t.Any],
    op_id: str,
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(name: str, headers: the_type) -> pipeline.Response:  # type: ignore
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == op_id, operations)),
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert id(hdrl.user_handler) == id(foo)
    assert hdrl.header_params
    msg = (
        'Detected usage of "headers" declared as typing.Any. '
        'axion will allow such declaration but be warned that '
        'you will loose all the help linters (like mypy) offer.'
    )
    assert msg in caplog.messages


@pytest.mark.parametrize('variation', (0, 1, 2, 3, 4, 5))
def test_invalid_headers_type(
    variation: int,
    mocker: ptm.MockFixture,
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

    async def foo(name: str, headers: Headers) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            foo,
            next(filter(lambda op: op.id == 'no_headers_op', operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert len(err.value) == 1


def test_oas_headers_signature_empty(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(name: str) -> pipeline.Response:
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'headers_op', operations)),
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    msg = (
        '"headers" found in operation but not in signature. '
        'Please double check that. axion cannot infer a correctness of '
        'this situations. If you wish to access any "headers" defined in '
        'specification, they have to be present in your handler '
        'as either "typing.Dict[str, typing.Any]", "typing.Mapping[str, typing.Any]" '
        'or typing_extensions.TypedDict[str, typing.Any].'
    )

    assert id(hdrl.user_handler) == id(foo)
    assert not hdrl.header_params
    assert msg in caplog.messages


def test_no_oas_headers_signature_empty(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(name: str) -> pipeline.Response:
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'no_headers_op', operations)),
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert id(hdrl.user_handler) == id(foo)
    assert not hdrl.header_params
    assert 'No "headers" in signature and operation parameters' in caplog.messages


def test_no_oas_headers_mapping(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(name: str, headers: t.Mapping[str, str]) -> pipeline.Response:
        ...

    hdrl = handler._resolve(
        foo,
        next(filter(lambda op: op.id == 'no_headers_op', operations)),
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert id(hdrl.user_handler) == id(foo)

    assert ('accept', 'accept') in hdrl.header_params.items()
    assert ('authorization', 'authorization') in hdrl.header_params.items()
    assert ('content-type', 'content_type') in hdrl.header_params.items()

    assert '"headers" found in signature but not in operation' in caplog.messages


def test_no_oas_headers_typed_dict_unknown_header(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    class EXTRA_INVALID(te.TypedDict):
        content_length: str

    async def extra_invalid(name: str, headers: EXTRA_INVALID) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            extra_invalid,
            next(filter(lambda op: op.id == 'no_headers_op', operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert len(err.value) == 1
    assert 'headers.content_length' in err.value
    assert err.value['headers.content_length'] == 'unknown'


@pytest.mark.parametrize('op_id', ('headers_op', 'no_headers_op'))
def test_typed_dict_bad_type(
    op_id: str,
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    class Invalid(te.TypedDict):
        accept: int

    async def goo(name: str, headers: Invalid) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            goo,
            next(filter(lambda op: op.id == op_id, operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert len(err.value) == 1
    assert 'headers.accept' in err.value
    assert err.value['headers.accept'] == 'expected [str], but got int'


def test_no_oas_headers_typed_dict(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    class CT(te.TypedDict):
        content_type: str

    class AUTH(te.TypedDict):
        authorization: str

    class ACCEPT(te.TypedDict):
        accept: str

    class FULL(CT, AUTH, ACCEPT):
        ...

    async def content_type(name: str, headers: CT) -> pipeline.Response:
        ...

    async def auth(name: str, headers: AUTH) -> pipeline.Response:
        ...

    async def accept(name: str, headers: ACCEPT) -> pipeline.Response:
        ...

    async def full(name: str, headers: FULL) -> pipeline.Response:
        ...

    for fn in (accept, auth, content_type, full):
        hdrl = handler._resolve(
            fn,
            next(filter(lambda op: op.id == 'no_headers_op', operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

        assert id(hdrl.user_handler) == id(fn)
        assert hdrl.header_params

        if fn is content_type:
            assert ('content-type', 'content_type') in hdrl.header_params.items()

            assert ('accept', 'accept') not in hdrl.header_params.items()
            assert ('authorization', 'authorization') not in hdrl.header_params.items()
        if fn is auth:
            assert ('authorization', 'authorization') in hdrl.header_params.items()

            assert ('accept', 'accept') not in hdrl.header_params.items()
            assert ('content-type', 'content_type') not in hdrl.header_params.items()
        if fn is accept:
            assert ('accept', 'accept') in hdrl.header_params.items()

            assert ('authorization', 'authorization') not in hdrl.header_params.items()
            assert ('content-type', 'content_type') not in hdrl.header_params.items()
        if fn is full:
            assert ('accept', 'accept') in hdrl.header_params.items()
            assert ('authorization', 'authorization') in hdrl.header_params.items()
            assert ('content-type', 'content_type') in hdrl.header_params.items()

        assert '"headers" found in signature but not in operation' in caplog.messages
        caplog.clear()


def test_oas_headers_signature_mapping(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(name: str, headers: t.Mapping[str, str]) -> pipeline.Response:
        ...

    operation = next(filter(lambda op: op.id == 'headers_op', operations))
    hdrl = handler._resolve(
        foo,
        operation,
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert id(hdrl.user_handler) == id(foo)
    assert hdrl.header_params

    assert ('accept', 'accept') in hdrl.header_params.items()
    assert ('authorization', 'authorization') in hdrl.header_params.items()
    assert ('content-type', 'content_type') in hdrl.header_params.items()
    assert ('x-trace-id', 'x_trace_id') in hdrl.header_params.items()
    assert '"headers" found both in signature and operation' in caplog.messages


def test_oas_headers_signature_typed_dict(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
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

    async def one(name: str, headers: One) -> pipeline.Response:
        ...

    async def two(name: str, headers: Two) -> pipeline.Response:
        ...

    async def three(name: str, headers: Three) -> pipeline.Response:
        ...

    async def full(name: str, headers: FULL) -> pipeline.Response:
        ...

    operation = next(filter(lambda op: op.id == 'headers_op', operations))
    for fn in (one, two, three, full):
        hdrl = handler._resolve(
            fn,
            operation,
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

        assert id(hdrl.user_handler) == id(fn)
        assert hdrl.header_params

        if fn is one:
            assert ('content-type', 'content_type') in hdrl.header_params.items()
            assert ('x-trace-id', 'x_trace_id') in hdrl.header_params.items()

            assert ('accept', 'accept') not in hdrl.header_params.items()
            assert ('authorization', 'authorization') not in hdrl.header_params.items()
        if fn is two:
            assert ('authorization', 'authorization') in hdrl.header_params.items()
            assert ('x-trace-id', 'x_trace_id') in hdrl.header_params.items()

            assert ('accept', 'accept') not in hdrl.header_params.items()
            assert ('content-type', 'content_type') not in hdrl.header_params.items()
        if fn is three:
            assert ('accept', 'accept') in hdrl.header_params.items()
            assert ('x-trace-id', 'x_trace_id') in hdrl.header_params.items()

            assert ('authorization', 'authorization') not in hdrl.header_params.items()
            assert ('content-type', 'content_type') not in hdrl.header_params.items()
        if fn is full:
            assert ('accept', 'accept') in hdrl.header_params.items()
            assert ('x-trace-id', 'x_trace_id') in hdrl.header_params.items()
            assert ('authorization', 'authorization') in hdrl.header_params.items()
            assert ('content-type', 'content_type') in hdrl.header_params.items()

        assert '"headers" found both in signature and operation' in caplog.messages
        caplog.clear()


def test_oas_headers_extra_header_typed_dict(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    class Invalid(te.TypedDict):
        user_agent: str
        x_trace_id: str

    async def goo(name: str, headers: Invalid) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            goo,
            next(filter(lambda op: op.id == 'headers_op', operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
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
    the_type: t.Type[t.Any],
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    class Invalid(te.TypedDict):
        x_trace_id: the_type  # type: ignore

    async def goo(name: str, headers: Invalid) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            goo,
            next(filter(lambda op: op.id == 'headers_op', operations)),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert len(err.value) == 1
    assert 'headers.x_trace_id' in err.value
    assert (f'expected [str], '
            f'but got {get_type_repr.get_repr(the_type)}'
            ) == err.value['headers.x_trace_id']
