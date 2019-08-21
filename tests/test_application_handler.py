import sys
import typing as t

import pytest

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


class TestAnalysisParameters:
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

    def test_signature_mismatch_missing(self) -> None:
        async def foo(
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> None:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._analyze(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'foo'
        assert len(err.value) == 1
        assert 'id' in err.value
        assert err.value['id'] == 'missing'

    def test_signature_all_missing(self) -> None:
        async def foo() -> None:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._analyze(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'foo'
        assert len(err.value) == 4
        for key in ('id', 'limit', 'page', 'include_extra'):
            assert key in err.value
            assert err.value[key] == 'missing'

    def test_signature_mismatch_bad_type(self) -> None:
        async def foo(
                id: bool,
                limit: t.Optional[int],
                page: t.Optional[float],
                include_extra: t.Optional[bool],
        ) -> None:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._analyze(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'foo'
        assert len(err.value) == 1
        assert 'id' in err.value
        assert repr(err.value['id']) == 'expected str, but got bool'

    @pytest.mark.skipif(
        sys.version_info < (3, 7),
        reason=(
            'This test case fails on 3.6 because typing signatures '
            'look different in 3.6 than in 3.7. '
            'This needs to be figured out in compatible way that '
            'provides actual markup used by user without hiding types '
            'carried in containers.'
            ' '
            'For example: '
            'In 3.7 repr(typing.List[bool]) == "typing.List[bool]" '
            'but in 3.6 that is "List"'
        ),
    )
    def test_signature_all_bad_type(self) -> None:
        async def foo(
                id: float,
                limit: t.Optional[t.Union[int, float]],
                page: t.Optional[t.AbstractSet[bool]],
                include_extra: t.Union[int, str],
        ) -> None:
            ...

        with pytest.raises(handler.InvalidHandlerError) as err:
            handler._analyze(
                handler=foo,
                operation=self.operation,
            )

        assert err.value.operation_id == 'foo'
        assert len(err.value) == 4
        for mismatch in err.value:
            if mismatch.param_name == 'id':
                assert repr(
                    err.value[mismatch.param_name],
                ) == 'expected str, but got float'
            elif mismatch.param_name == 'limit':
                assert repr(
                    err.value[mismatch.param_name],
                ) == 'expected typing.Optional[int], but got typing.Optional[float,int]'
            elif mismatch.param_name == 'page':
                assert repr(
                    err.value[mismatch.param_name],
                ) == (
                    'expected typing.Optional[float], but got '
                    'typing.Optional[typing.AbstractSet[bool]]'
                )
            elif mismatch.param_name == 'include_extra':
                assert repr(
                    err.value[mismatch.param_name],
                ) == ('expected typing.Optional[bool], but got '
                      'typing.Union[int,str]')

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
