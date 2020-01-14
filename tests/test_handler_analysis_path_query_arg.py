import typing as t

import pytest

from axion import handler
from axion import response
from axion.oas import parser

operation = next(
    iter(
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
    ),
)


def test_signature_mismatch_missing() -> None:
    async def foo(
            limit: t.Optional[int],
            page: t.Optional[float],
            include_extra: t.Optional[bool],
    ) -> response.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=foo,
            operation=operation,
        )

    assert err.value.operation_id == 'TestAnalysisParameters'
    assert len(err.value) == 1
    assert 'id' in err.value
    assert err.value['id'] == 'missing'


def test_signature_all_missing() -> None:
    async def foo() -> response.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=foo,
            operation=operation,
        )

    assert err.value.operation_id == 'TestAnalysisParameters'
    assert len(err.value) == 4
    for key in ('id', 'limit', 'page', 'includeExtra'):
        assert key in err.value
        assert err.value[key] == 'missing'


def test_signature_mismatch_bad_type() -> None:
    async def foo(
            id: bool,
            limit: t.Optional[int],
            page: t.Optional[float],
            include_extra: t.Optional[bool],
    ) -> response.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=foo,
            operation=operation,
        )

    assert err.value.operation_id == 'TestAnalysisParameters'
    assert len(err.value) == 1
    assert 'id' in err.value
    assert err.value['id'] == 'expected [str], but got bool'


def test_signature_all_bad_type() -> None:
    async def foo(
            id: float,
            limit: t.Optional[t.Union[int, float]],
            page: t.Optional[t.AbstractSet[bool]],
            include_extra: t.Union[int, str],
    ) -> response.Response:
        ...

    with pytest.raises(handler.InvalidHandlerError) as err:
        handler._resolve(
            handler=foo,
            operation=operation,
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


def test_signature_match() -> None:
    async def test_handler(
            id: str,
            limit: t.Optional[int],
            page: t.Optional[float],
            include_extra: t.Optional[bool],
    ) -> response.Response:
        ...

    hdrl = handler._resolve(
        handler=test_handler,
        operation=operation,
    )

    assert len(hdrl.path_params) == 1
    assert len(hdrl.query_params) == 3
