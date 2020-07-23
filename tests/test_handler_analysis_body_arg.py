import typing as t

from _pytest import logging
import pytest
import pytest_mock as ptm
import typing_extensions as te

from axion import handler
from axion.oas import model
from axion.oas import parser


class R(te.TypedDict):
    http_code: int
    body: te.Literal[None]


def test_no_request_body_empty_signature(mocker: ptm.MockFixture) -> None:
    async def test() -> R:
        ...

    hdrl = handler._resolve(
        handler=test,
        operation=_make_operation(None),
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert not hdrl.has_body


@pytest.mark.parametrize('required', (True, False))
def test_request_body_signature_set(required: bool, mocker: ptm.MockFixture) -> None:
    async def test(body: t.Dict[str, t.Any]) -> R:
        ...

    hdrl = handler._resolve(
        handler=test,
        operation=_make_operation({
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
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert hdrl.has_body


def test_request_body_required_signature_optional(mocker: ptm.MockFixture) -> None:
    async def test(body: t.Optional[t.Dict[str, t.Any]]) -> R:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation({
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
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
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
def test_request_body_different_types(the_type: t.Any, mocker: ptm.MockFixture) -> None:
    async def test(body: the_type) -> R:  # type: ignore
        ...

    hdrl = handler._resolve(
        handler=test,
        operation=_make_operation({
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
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert hdrl.has_body


def test_no_request_body_signature_set(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def test(body: t.Dict[str, t.Any]) -> R:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=test,
            operation=_make_operation(None),
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
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
    required: bool,
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo() -> R:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=foo,
            operation=_make_operation({
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
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert err.value
    assert 1 == len(err.value)
    assert 'body' in err.value
    assert 'missing' == err.value['body']

    assert (
        'Operation defines a request body, but it is not specified in '
        'handler signature'
    ) in caplog.messages


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
