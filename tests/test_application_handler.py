import typing as t

import pytest
import pytest_mock as ptm

from axion.application import handler
from axion.specification import model
from axion.specification import parser


def normal_f() -> None:
    ...


async def async_f() -> None:
    ...


def test_resolve_handler_module_not_found() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(model.OASOperationId('really_dummy.api.get_all'))
    assert err.match('Failed to import module=really_dummy.api')


def test_resolve_handler_function_not_found() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(model.OASOperationId('tests.test_application_handler.foo'))
    assert err.match(
        'Failed to locate function=foo in module=tests.test_application_handler',
    )


def test_resolve_handler_not_couroutine() -> None:
    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(model.OASOperationId('tests.test_application_handler.normal_f'))
    assert err.match(
        'tests.test_application_handler.normal_f did not resolve to coroutine',
    )


def test_resolve_handler_couroutine() -> None:
    assert handler._resolve(
        model.OASOperationId('tests.test_application_handler.async_f'),
    ) is async_f


class TestAnalysisPathQueryParameters:
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

    def test_signature_mismatch(self) -> None:
        handler._analyze(
            handler=test_handler,
            operation=self.operation,
        )

    def test_signature_match(self) -> None:
        async def test_handler(
                id: str,
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> None:
            ...

        handler._analyze(
            handler=test_handler,
            operation=self.operation,
        )
