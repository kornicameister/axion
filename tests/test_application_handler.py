import typing as t

import pytest
import pytest_mock as ptm

from axion.application import handler
from axion.specification import parser


def normal_f() -> None:
    ...


async def async_f() -> None:
    ...


def test_resolve_handler_module_not_found() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve('really_dummy.api.get_all')
    assert err.match('Failed to import module=really_dummy.api')


def test_resolve_handler_function_not_found() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve('tests.test_application_handler.foo')
    assert err.match(
        'Failed to locate function=foo in module=tests.test_application_handler',
    )


def test_resolve_handler_not_couroutine() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve('tests.test_application_handler.normal_f')
    assert err.match(
        'tests.test_application_handler.normal_f did not resolve to coroutine',
    )


def test_resolve_handler_couroutine() -> None:
    assert handler._resolve('tests.test_application_handler.async_f') is async_f


def test_analyze_handler(mocker: ptm.MockFixture) -> None:
    async def get_one(
            id: str,
            limit: t.Optional[int],
            include_extra: t.Optional[bool],
    ) -> None:
        ...

    operation = list(
        parser._resolve_operations(
            components={},
            paths={
                '/{name}': {
                    'post': {
                        'operationId': 'foo',
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

    handler._analyze(
        handler=get_one,
        operation=operation,
    )
