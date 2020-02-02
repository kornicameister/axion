from axion.oas import functions
from axion.oas import model
from axion.oas import parser


def test_simple_schema() -> None:
    dvs = functions.parameter_default_values(
        parser._resolve_parameter(
            components={},
            param_name='app_id',
            param_def={
                'schema': {
                    'type': 'string',
                    'default': __name__,
                },
                'required': True,
            },
            param_in=model.OASPathParameter,
        ),
    )

    assert dvs
    assert len(dvs) == 1
    assert dvs[0] == __name__


def test_complex_schema() -> None:
    dvs = functions.parameter_default_values(
        parser._resolve_parameter(
            components={},
            param_name='app_id',
            param_def={
                'content': {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'name': {
                                    'type': 'string',
                                },
                            },
                            'default': {
                                'name': __name__,
                            },
                        },
                    },
                },
            },
            param_in=model.OASQueryParameter,
        ),
    )

    assert dvs
    assert len(dvs) == 1
    assert dvs[0] == {'name': __name__}
