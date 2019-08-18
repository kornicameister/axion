import typing as t

import pytest

from axion.specification import model
from axion.specification import parser


@pytest.mark.parametrize(
    (
        'properties',
        'additional_properties',
        'expected_result',
    ),
    (
        ({}, True, True),
        ({}, False, False),
        ({}, {}, True),
        ({}, {
            'type': 'string',
        }, False),
        ({}, {
            'type': 'number',
        }, False),
        ({
            'foo': {
                'type': 'string',
            },
        }, {}, False),
    ),
)
def test_spec_oas_object_free_form(
        properties: t.Optional[t.Dict[str, t.Any]],
        additional_properties: t.Union[bool, model.OASType],
        expected_result: bool,
) -> None:
    assert parser._build_oas_object({}, {
        'additionalProperties': additional_properties,
        'properties': properties,
    }).is_free_form is expected_result
