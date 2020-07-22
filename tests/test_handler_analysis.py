import typing as t

from _pytest import logging
import pytest
import pytest_mock as ptm

from axion import handler
from axion import pipeline
from axion.oas import model
from axion.oas import parser


def normal_f() -> pipeline.Response:
    ...


async def async_f() -> pipeline.Response:
    ...


@pytest.mark.parametrize(
    'operation_id,error_msg',
    (
        (
            'really_dummy.api.get_all',
            'Failed to import module=really_dummy.api',
        ),
        (
            f'{__name__}.foo',
            f'Failed to locate function=foo in module={__name__}',
        ),
        (
            f'{normal_f.__module__}.{normal_f.__name__}',
            f'{normal_f.__module__}.{normal_f.__name__} did not resolve to coroutine',
        ),
    ),
)
def test_make_handler_bad_cases(
    operation_id: str,
    error_msg: str,
    mocker: ptm.MockFixture,
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
        handler.resolve(
            operation,
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
            asynchronous=True,
        )
    assert err.match(error_msg)


def test_resolve_handler_couroutine() -> None:
    assert handler._import(
        model.OASOperationId(f'{async_f.__module__}.{async_f.__name__}'),
        asynchronous=True,
    ) is async_f


def test_empty_handler_signature(
    mocker: ptm.MockFixture,
    caplog: logging.LogCaptureFixture,
) -> None:
    async def foo() -> pipeline.Response:
        ...

    handler._resolve(
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
        request_processor=mocker.Mock(),
        response_processor=mocker.Mock(),
    )

    assert 'TestAnalysisNoParameters does not declare any parameters' in caplog.messages


def test_not_empty_signature(
    caplog: logging.LogCaptureFixture,
    mocker: ptm.MockFixture,
) -> None:
    async def foo(
        name: str,
        foo: str,
        bar: str,
        lorem_ipsum: t.List[str],
    ) -> pipeline.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
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
            request_processor=mocker.Mock(),
            response_processor=mocker.Mock(),
        )

    assert len(err.value) == 3

    assert err.value['foo'] == 'unexpected'
    assert err.value['bar'] == 'unexpected'
    assert err.value['lorem_ipsum'] == 'unexpected'

    assert (
        'Unconsumed arguments [foo, bar, lorem_ipsum] detected in Thor handler signature'
        in caplog.messages
    )
