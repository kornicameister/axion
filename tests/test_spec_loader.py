from pathlib import Path
import typing as t

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm

from axion import spec


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


def test_spec_render_complex_schema() -> None:
    the_spec = spec.load(Path('tests/specifications/complex.yml'))

    assert the_spec.raw_spec
    assert len(the_spec.operations) == 4
