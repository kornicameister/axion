import typing as t

import pytest

from axion.oas import model
from axion.oas.parser import type as parse_type


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
def test_free_form(
    properties: t.Optional[t.Dict[str, t.Any]],
    additional_properties: t.Union[bool, model.OASType[t.Any]],
    expected_result: bool,
) -> None:
    oas_object = parse_type.resolve(
        {},
        {
            'type': 'object',
            'additionalProperties': additional_properties,
            'properties': properties,
        },
    )

    assert isinstance(oas_object, model.OASObjectType)
    assert oas_object.is_free_form is expected_result


def test_discriminator() -> None:
    oas_object = parse_type.resolve(
        {},
        {
            'type': 'object',
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
    assert isinstance(oas_object, model.OASObjectType)

    assert oas_object.discriminator
    assert oas_object.discriminator.property_name == 'petType'
    assert not oas_object.discriminator.mapping


@pytest.mark.parametrize(
    'additional_properties,should_raise',
    ((True, False), (False, True)),
)
def test_discriminator_and__additional_properties(
    additional_properties: bool,
    should_raise: bool,
) -> None:
    try:
        parse_type.resolve(
            {},
            {
                'type': 'object',
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


def test_correct_python_type() -> None:
    assert issubclass(
        parse_type.resolve(
            {},
            {
                'type': 'object',
            },
        ).python_type,
        dict,
    )


def test_oas_type() -> None:
    assert parse_type.resolve({}, {'type': 'object'}).oas_type == 'object'
