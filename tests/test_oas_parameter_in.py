import typing as t

import pytest

from axion.oas import functions
from axion.oas import model
from axion.oas import parser


@pytest.mark.parametrize(
    'param_in,param_loc',
    (
        (model.OASPathParameter, 'path'),
        (model.OASQueryParameter, 'query'),
        (model.OASHeaderParameter, 'header'),
        (model.OASCookieParameter, 'cookie'),
    ),
)
def test_paramter_in(
    param_in: t.Any,
    param_loc: str,
) -> None:
    assert functions.parameter_in(
        parser._resolve_parameter(
            components={},
            param_name='app_id',
            param_def={
                'schema': {
                    'type': 'string',
                },
                'required': True,
            },
            param_in=param_in,
        ),
    ) == param_loc
