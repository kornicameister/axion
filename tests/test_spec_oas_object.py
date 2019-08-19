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
        additional_properties: t.Union[bool, model.OASType[t.Any]],
        expected_result: bool,
) -> None:
    assert parser._build_oas_object({}, {
        'additionalProperties': additional_properties,
        'properties': properties,
    }).is_free_form is expected_result


def test_spec_oas_object_discriminator() -> None:
    oas_object = parser._build_oas_object(
        {},
        {
            'discriminator': {
                'propertyName': 'petType',
            },
            'properties': {
                'name': {
                    'type': 'string',
                },
                'petType': {
                    'type': 'string',
                },
            },
            'required': [
                'name',
                'petType',
            ],
        },
    )
    assert oas_object.discriminator
    assert oas_object.discriminator.property_name == 'petType'
    assert oas_object.discriminator.mapping is None


@pytest.mark.parametrize(
    'additional_properties,should_raise',
    ((True, False), (False, True)),
)
def test_spec_oas_object_discriminator_property_additional_properties(
        additional_properties: bool,
        should_raise: bool,
) -> None:
    try:
        parser._build_oas_object(
            {},
            {
                'discriminator': {
                    'propertyName': 'petTypee',
                },
                'additionalProperties': additional_properties,
                'properties': {
                    'name': {
                        'type': 'string',
                    },
                    'petType': {
                        'type': 'string',
                    },
                },
                'required': [
                    'name',
                    'petType',
                ],
            },
        )
    except ValueError as err:
        if should_raise:
            assert err.args[
                0
            ] == 'Discriminator petTypee not found in object properties [name, petType]'
        else:
            raise AssertionError(
                'If additionalProperties==true discriminator may be found in them, '
                'therefore this exception should not occur.',
            )
