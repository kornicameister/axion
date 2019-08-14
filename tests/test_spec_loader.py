from pathlib import Path
import typing as t

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm

from axion import spec
from axion.spec import model


def test_spec_is_just_invalid(tmp_path: Path) -> None:
    spec_path = tmp_path / 'openapi.yml'
    with spec_path.open('w') as h:
        h.write("""
---
openapi: '3.0.0'
info: {}
        """)
    with pytest.raises(osv.exceptions.OpenAPIValidationError):
        spec.load(spec_path)


def test_spec_load_from_path(
        spec_path: Path,
        mocker: ptm.MockFixture,
) -> None:
    parse_spec = mocker.spy(spec, '_parse_spec')
    assert spec.load(spec_path) is not None
    parse_spec.assert_called_once()


def test_spec_load_from_unsupported_type(mocker: ptm.MockFixture) -> None:
    parse_spec = mocker.spy(spec, '_parse_spec')
    with pytest.raises(ValueError):
        spec.load(1)  # type: ignore
    assert not parse_spec.called


@pytest.mark.parametrize(('ref', 'expected_def'), [
    (
        '#/components/schemas/Category',
        {
            'type': 'object',
            'properties': {
                'id': {
                    'type': 'integer',
                    'format': 'int64',
                },
                'name': {
                    'type': 'string',
                },
            },
        },
    ),
    (
        '#/components/schemas/UltraCategory',
        {
            'type': 'object',
            'properties': {
                'id': {
                    'type': 'integer',
                    'format': 'int64',
                },
                'name': {
                    'type': 'string',
                },
            },
        },
    ),
    (
        '#/components/securitySchemes/apiKey',
        {
            'type': 'apiKey',
            'name': 'api_key',
            'in': 'header',
        },
    ),
    (
        '#/components/responses/NotFound',
        {
            'description': 'Entity not found.',
        },
    ),
    (
        '#/components/parameters/limitParam',
        {
            'name': 'limit',
            'in': 'query',
            'description': 'max records to return',
            'required': True,
            'schema': {
                'type': 'integer',
                'format': 'int32',
            },
        },
    ),
    (
        '#/components/headers/X-Rate-Limit',
        {
            'description': 'Rate limit for this API',
            'required': True,
            'schema': {
                'type': 'integer',
                'format': 'int32',
            },
        },
    ),
    (
        '#/components/requestBodies/Example',
        {
            'description': 'category to add to the system',
            'content': {
                'application/json': {
                    'schema': {
                        '$ref': '#/components/schemas/Category',
                    },
                    'examples': {
                        'user': {
                            'summary': 'Category Example',
                            'externalValue': 'http://category-example.json',
                        },
                    },
                },
            },
        },
    ),
])
def test_spec_load_follow_ref(
        ref: str,
        expected_def: t.Dict[str, t.Any],
) -> None:
    components = {
        'requestBodies': {
            'Example': {
                'description': 'category to add to the system',
                'content': {
                    'application/json': {
                        'schema': {
                            '$ref': '#/components/schemas/Category',
                        },
                        'examples': {
                            'user': {
                                'summary': 'Category Example',
                                'externalValue': 'http://category-example.json',
                            },
                        },
                    },
                },
            },
        },
        'schemas': {
            'Category': {
                'type': 'object',
                'properties': {
                    'id': {
                        'type': 'integer',
                        'format': 'int64',
                    },
                    'name': {
                        'type': 'string',
                    },
                },
            },
            'UltraCategory': {
                '$ref': '#/components/schemas/Category',
            },
        },
        'headers': {
            'X-Rate-Limit': {
                'description': 'Rate limit for this API',
                'required': True,
                'schema': {
                    'type': 'integer',
                    'format': 'int32',
                },
            },
        },
        'parameters': {
            'limitParam': {
                'name': 'limit',
                'in': 'query',
                'description': 'max records to return',
                'required': True,
                'schema': {
                    'type': 'integer',
                    'format': 'int32',
                },
            },
        },
        'responses': {
            'NotFound': {
                'description': 'Entity not found.',
            },
        },
        'securitySchemes': {
            'apiKey': {
                'type': 'apiKey',
                'name': 'api_key',
                'in': 'header',
            },
        },
    }
    assert expected_def == spec._follow_ref(components, ref)


def test_spec_load_follow_ref_no_such_ref() -> None:
    with pytest.raises(KeyError):
        spec._follow_ref({}, '#/components/schemas/Dummy')


def test_spec_render_complex_schema() -> None:
    the_spec, raw_spec = spec.load(Path('tests/specifications/complex.yml'))

    # keys of expected operations
    rings_get_key = model.OperationKey(
        path='/rings',
        http_method=model.HTTPMethod.GET,
    )
    rings_post_key = model.OperationKey(
        path='/rings',
        http_method=model.HTTPMethod.POST,
    )
    ring_one_get_key = model.OperationKey(
        path='/rings/{ring_id}',
        http_method=model.HTTPMethod.GET,
    )
    ring_one_put_key = model.OperationKey(
        path='/rings/{ring_id}',
        http_method=model.HTTPMethod.PUT,
    )

    # asserting
    assert raw_spec
    assert the_spec.version
    assert len(the_spec.operations) == 4
    for op_key in (
            rings_get_key,
            rings_post_key,
            ring_one_get_key,
            ring_one_put_key,
    ):
        assert op_key in the_spec.operations, f'{op_key} not resolved in spec'
        operations = the_spec.operations[op_key]
        # validate per operation
        if op_key == rings_get_key:
            assert len(operations) == 1
            assert not operations[0].deprecated
            assert len(operations[0].responses) == 3
            assert len(operations[0].parameters) == 3
        elif op_key == rings_post_key:
            assert len(operations) == 1
            assert not operations[0].deprecated
            assert len(operations[0].responses) == 4
            assert len(operations[0].parameters) == 2
        elif op_key == ring_one_get_key:
            assert len(operations) == 1
            assert not operations[0].deprecated
            assert len(operations[0].responses) == 7
            assert len(operations[0].parameters) == 4
        elif op_key == ring_one_put_key:
            assert len(operations) == 1
            assert operations[0].deprecated
            assert len(operations[0].responses) == 3
            assert len(operations[0].parameters) == 2
        else:
            raise AssertionError('This should not happen')
