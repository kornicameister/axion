from pathlib import Path
import typing as t

import pytest
import yarl

from axion.specification import loader
from axion.specification import model
from axion.specification import parser


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
    assert expected_def == parser._follow_ref(components, ref)


def test_spec_load_follow_ref_no_such_ref() -> None:
    with pytest.raises(KeyError):
        parser._follow_ref({}, '#/components/schemas/Dummy')


@pytest.mark.parametrize(
    'param_name,param_in,expected_param_name',
    (
        ('appName', model.OASHeaderParameter, 'appName'),
        ('appName', model.OASQueryParameter, 'app_name'),
        ('appName', model.OASPathParameter, 'app_name'),
        ('appName', model.OASCookieParameter, 'appName'),
    ),
)
def test_spec_snake_case_behavior(
        param_name: str,
        param_in: t.Type[t.Any],
        expected_param_name: str,
) -> None:
    param_def = {
        'required': True,
        'schema': {
            'type': 'string',
        },
    }
    param = parser._resolve_parameter(
        components={},
        param_name=param_name,
        param_def=param_def,
        param_in=param_in,
    )
    assert param.name == expected_param_name


def test_spec_resolve_param_path() -> None:
    param_def = {
        'schema': {
            'type': 'string',
        },
        'style': 'simple',
        'explode': True,
        'required': True,
        'deprecated': True,
        'example': 'Test',
    }
    path = parser._resolve_parameter(
        components={},
        param_name='app_id',
        param_def=param_def,
        param_in=model.OASPathParameter,
    )
    assert isinstance(path.schema, tuple)

    assert isinstance(path.schema[0], model.OASStringType)
    assert path.schema[1] == model.ParameterStyles['simple']

    assert path.explode
    assert path.deprecated
    assert path.required
    assert path.example == 'Test'


def test_spec_resolve_param_path_required_is_false() -> None:
    param_def = {
        'schema': {
            'type': 'string',
        },
        'style': 'simple',
        'explode': True,
        'required': False,
        'deprecated': True,
        'example': 'Test',
    }
    with pytest.raises(ValueError) as err:
        parser._resolve_parameter(
            components={},
            param_name='app_id',
            param_def=param_def,
            param_in=model.OASPathParameter,
        )
    assert err.match('Path parameter app_id must have required set to True')


def test_spec_resolve_param_header() -> None:
    param_def = {
        'schema': {
            'type': 'string',
        },
        'style': 'simple',
        'explode': True,
        'required': True,
        'deprecated': True,
        'example': 'Test',
    }
    header = parser._resolve_parameter(
        components={},
        param_name='X-Trace-Id',
        param_def=param_def,
        param_in=model.OASHeaderParameter,
    )
    assert isinstance(header.schema, tuple)

    assert isinstance(header.schema[0], model.OASStringType)
    assert header.schema[1] == model.ParameterStyles['simple']

    assert header.explode
    assert header.deprecated
    assert header.required
    assert header.example == 'Test'


@pytest.mark.parametrize('param_name', ('Content-Type', 'Accept', 'Authorization'))
def test_spec_resolve_param_header_invalid_name(param_name: str) -> None:
    param_def = {
        'schema': {
            'type': 'string',
        },
        'style': 'simple',
        'explode': True,
        'required': True,
        'deprecated': True,
        'example': 'Test',
    }
    with pytest.raises(ValueError) as err:
        parser._resolve_parameter(
            components={},
            param_name=param_name,
            param_def=param_def,
            param_in=model.OASHeaderParameter,
        )
    assert err.match(f'Header parameter name {param_name} is reserved thus invalid')


def test_spec_render_complex_schema() -> None:
    spec_location = Path('tests/specifications/complex.yml')
    loaded_spec = loader.load_spec(spec_location)

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
            lambda op: op and op.id == 'frodo.lotr.rings.get_all',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_make_one_op = next(
        filter(
            lambda op: op and op.id == 'frodo.lotr.rings.make_one',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_put_one_op = next(
        filter(
            lambda op: op and op.id == 'frodo.lotr.rings.put_one',
            loaded_spec.operations,
        ),
        None,
    )  # type: t.Optional[model.Operation]
    rings_get_one_op = next(
        filter(
            lambda op: op and op.id == 'frodo.lotr.rings.get_one',
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
