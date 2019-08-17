from pathlib import Path
import typing as t

import openapi_spec_validator as osv
import pytest
import pytest_mock as ptm
import yarl

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
    spec_location = Path('tests/specifications/complex.yml')
    loaded_spec = spec.load(spec_location)

    # asserting
    assert loaded_spec.version

    # assert servers
    assert len(loaded_spec.servers) == 1
    assert loaded_spec.servers[0].url == 'http://lotr-service'
    assert not loaded_spec.servers[0].variables

    # assert that 4 operations were loaded
    assert len(loaded_spec.operations) == 4

    rings_get_all_op = next(
        filter(
            lambda op: op and op.operation_id == 'frodo.lotr.rings.get_all',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_make_one_op = next(
        filter(
            lambda op: op and op.operation_id == 'frodo.lotr.rings.make_one',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_put_one_op = next(
        filter(
            lambda op: op and op.operation_id == 'frodo.lotr.rings.put_one',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_get_one_op = next(
        filter(
            lambda op: op and op.operation_id == 'frodo.lotr.rings.get_one',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]

    assert rings_get_all_op
    assert rings_get_all_op.path == yarl.URL('/rings')
    assert rings_get_all_op.http_method == model.HTTPMethod.GET
    assert not rings_get_all_op.deprecated
    assert len(rings_get_all_op.responses) == 3
    assert 200 in rings_get_all_op.responses
    assert 400 in rings_get_all_op.responses
    assert 'default' in rings_get_all_op.responses
    assert len(rings_get_all_op.parameters) == 3

    assert rings_make_one_op
    assert rings_make_one_op.path == yarl.URL('/rings')
    assert rings_make_one_op.http_method == model.HTTPMethod.POST
    assert not rings_make_one_op.deprecated
    assert len(rings_make_one_op.responses) == 4
    assert 201 in rings_make_one_op.responses
    assert 404 in rings_make_one_op.responses
    assert 409 in rings_make_one_op.responses
    assert 'default' in rings_make_one_op.responses
    assert len(rings_make_one_op.parameters) == 2

    assert rings_put_one_op
    assert rings_put_one_op.path == yarl.URL('/rings/{ring_id}')
    assert rings_put_one_op.http_method == model.HTTPMethod.PUT
    assert rings_put_one_op.deprecated
    assert len(rings_put_one_op.responses) == 3
    assert 201 in rings_put_one_op.responses
    assert 204 in rings_put_one_op.responses
    assert 400 in rings_put_one_op.responses
    assert len(rings_put_one_op.parameters) == 2

    assert rings_get_one_op
    assert rings_get_one_op.path == yarl.URL('/rings/{ring_id}')
    assert rings_get_one_op.http_method == model.HTTPMethod.GET
    assert not rings_get_one_op.deprecated
    assert len(rings_get_one_op.responses) == 7
    assert 200 in rings_get_one_op.responses
    assert 400 in rings_get_one_op.responses
    assert 404 in rings_get_one_op.responses
    assert 408 in rings_get_one_op.responses
    assert 422 in rings_get_one_op.responses
    assert 503 in rings_get_one_op.responses
    assert 'default' in rings_get_one_op.responses
    assert len(rings_get_one_op.parameters) == 4
