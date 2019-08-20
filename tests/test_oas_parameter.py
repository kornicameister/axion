import typing as t

import pytest

from axion.specification import model
from axion.specification import parser


@pytest.mark.parametrize(
    'param_name,param_in,expected_param_name',
    (
        ('appName', model.OASHeaderParameter, 'appName'),
        ('appName', model.OASQueryParameter, 'app_name'),
        ('appName', model.OASPathParameter, 'app_name'),
        ('appName', model.OASCookieParameter, 'appName'),
    ),
)
def test_param_snake_case(
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


def test_path_param_resolve() -> None:
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


def test_path_param_path_required_false() -> None:
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


def test_header_param_resolve() -> None:
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
def test_header_param_invalid_name(param_name: str) -> None:
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


@pytest.mark.parametrize(
    'param_in',
    (
        model.OASPathParameter,
        model.OASHeaderParameter,
        model.OASQueryParameter,
        model.OASCookieParameter,
    ),
)
@pytest.mark.parametrize(
    'oas_type, python_type',
    (('string', str), ('number', float), ('integer', int), ('boolean', bool)),
)
def test_param_python_type(
        oas_type: str,
        param_in: t.Type[t.Any],
        python_type: t.Type[t.Any],
) -> None:
    param = parser._resolve_parameter(
        components={},
        param_name='foo',
        param_in=param_in,
        param_def={
            'required': True,
            'schema': {
                'type': oas_type,
            },
        },
    )
    assert param.python_type == python_type
