import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import model
from axion.specification.parser import type as parse_type


@pytest.mark.parametrize(
    'mix_key',
    ('oneOf', 'anyOf'),
)
@pytest.mark.parametrize(
    'in_mix,expected_schemas',
    # yapf: disable
    (
        (
            [{
                'type': 'string',
            }],
            [(True, model.OASStringType)],
        ),
        (
            [
                {
                    'type': 'string',
                },
                {
                    'type': 'number',
                },
                {
                    'not': {
                        'type': 'boolean',
                    },
                },
            ],
            [
                (True, model.OASStringType),
                (True, model.OASNumberType),
                (False, model.OASBooleanType),
            ],
        ),
        (
            [
                {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                        },
                    },
                },
                {
                    'description': 'Test',
                },
            ],
            [
                (True, model.OASObjectType),
                (True, model.OASAnyType),
            ],
        ),
    ),
    # yapf: enable
)
def test_any_one_of(
        mix_key: str,
        in_mix: t.List[t.Dict[str, t.Any]],
        expected_schemas: t.List[t.Tuple[bool, t.Type[model.OASType[t.Any]]]],
) -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            mix_key: in_mix,
        },
    )

    assert isinstance(mix_type, (model.OASAnyOfType, model.OASOneOfType))
    assert len(mix_type.schemas) == len(in_mix)
    assert list(
        map(
            lambda v: (v[0], type(v[1])),
            mix_type.schemas,
        ),
    ) == expected_schemas


def test_any_of_is_any() -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            'anyOf': [
                {
                    'type': 'string',
                },
                {
                    'type': 'number',
                },
                {
                    'type': 'integer',
                },
                {
                    'type': 'boolean',
                },
                {
                    'type': 'array',
                    'items': {},
                },
                {
                    'type': 'object',
                },
            ],
        },
    )
    assert isinstance(mix_type, model.OASAnyType)


def test_all_of_more_than_one_type() -> None:
    with pytest.raises(exceptions.OASConflict):
        parse_type.resolve(
            components={},
            work_item={
                'allOf': [
                    {
                        'type': 'string',
                    },
                    {
                        'type': 'number',
                    },
                ],
            },
        )


@pytest.mark.parametrize('oas_type', ('number', 'integer'))
def test_all_of_integer(oas_type: str) -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            'default': 4 if oas_type == 'integer' else 4.0,
            'example': 2 if oas_type == 'integer' else 2.0,
            'allOf': [
                {
                    'minimum': 2 if oas_type == 'integer' else 2.0,
                },
                {
                    'maximum': 10 if oas_type == 'integer' else 10.0,
                },
                {
                    'multipleOf': 2 if oas_type == 'integer' else 2.0,
                },
                {
                    'type': oas_type,
                    'deprecated': False,
                },
            ],
        },
    )
    assert isinstance(mix_type, model.OASNumberType)
    assert issubclass(
        mix_type.number_cls,
        int if oas_type == 'integer' else float,
    )

    assert (2 if oas_type == 'integer' else 2.0) == mix_type.minimum
    assert (10 if oas_type == 'integer' else 10.0) == mix_type.maximum

    assert (4 if oas_type == 'integer' else 4.0) == mix_type.default
    assert (2 if oas_type == 'integer' else 2.0) == mix_type.example
    assert (2 if oas_type == 'integer' else 2.0) == mix_type.multiple_of

    assert not mix_type.deprecated


def test_all_of_object() -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            'allOf': [
                {
                    'type': 'object',
                    'required': [
                        'name',
                    ],
                    'properties': {
                        'name': {
                            'type': 'string',
                        },
                    },
                },
                {
                    'properties': {
                        'lastName': {
                            'type': 'string',
                        },
                    },
                },
                {
                    'deprecated': True,
                    'required': [
                        'lastName',
                    ],
                },
                {
                    'required': [
                        'name',
                        'lastName',
                        'fullName',
                    ],
                    'properties': {
                        'lastName': {
                            'type': 'string',
                            'writeOnly': True,
                            'deprecated': True,
                        },
                        'name': {
                            'type': 'string',
                            'writeOnly': True,
                            'deprecated': True,
                        },
                        'fullName': {
                            'type': 'string',
                            'writeOnly': True,
                        },
                    },
                },
            ],
        },
    )

    assert isinstance(mix_type, model.OASObjectType)
    assert 3 == len(mix_type.properties)

    assert 'name' in mix_type.properties
    assert isinstance(mix_type.properties['name'], model.OASStringType)
    assert mix_type.properties['name'].write_only
    assert mix_type.properties['name'].deprecated

    assert isinstance(mix_type.properties['fullName'], model.OASStringType)
    assert mix_type.properties['fullName'].write_only
    assert not mix_type.properties['fullName'].deprecated

    assert isinstance(mix_type.properties['lastName'], model.OASStringType)
    assert mix_type.properties['lastName'].write_only
    assert mix_type.properties['lastName'].deprecated

    assert 3 == len(mix_type.required)
    assert 'lastName' in mix_type.required
    assert 'name' in mix_type.required

    assert mix_type.deprecated


def test_all_of_object_with_ref() -> None:
    mix_type = parse_type.resolve(
        components={
            'schemas': {
                'Hammer': {
                    'type': 'object',
                    'required': ['weight'],
                    'properties': {
                        'weight': {
                            'type': 'number',
                        },
                    },
                },
            },
        },
        work_item={
            'allOf': [
                {
                    '$ref': '#/components/schemas/Hammer',
                },
                {
                    'properties': {
                        'isMighty': {
                            'type': 'boolean',
                        },
                    },
                },
            ],
        },
    )

    assert isinstance(mix_type, model.OASObjectType)
    assert 2 == len(mix_type.properties)

    assert 'weight' in mix_type.properties
    assert isinstance(mix_type.properties['weight'], model.OASNumberType)

    assert 'isMighty' in mix_type.properties
    assert isinstance(mix_type.properties['isMighty'], model.OASBooleanType)


def test_all_of_array() -> None:
    mix_type = parse_type.resolve(
        components={
            'schemas': {
                'Hammer': {
                    'type': 'object',
                    'required': ['weight'],
                    'properties': {
                        'weight': {
                            'type': 'number',
                        },
                    },
                },
            },
        },
        work_item={
            'nullable': True,
            'readOnly': True,
            'writeOnly': False,
            'allOf': [
                {
                    'type': 'array',
                    'items': {
                        '$ref': '#/components/schemas/Hammer',
                    },
                },
                {
                    'uniqueItems': True,
                },
            ],
        },
    )

    assert isinstance(mix_type, model.OASArrayType)
    assert isinstance(mix_type.items_type, model.OASObjectType)

    assert mix_type.unique_items

    assert mix_type.nullable
    assert mix_type.read_only
    assert not mix_type.write_only
