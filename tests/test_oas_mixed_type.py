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


@pytest.mark.parametrize(
    'oas_type',
    ('string', 'number', 'integer', 'array', 'boolean', 'object'),
)
@pytest.mark.parametrize(
    'prop_key,prop_value',
    (
        ('readOnly', True),
        ('readOnly', False),
        ('writeOnly', True),
        ('writeOnly', False),
        ('deprecated', True),
        ('deprecated', False),
    ),
)
def test_all_of_conflict_in_value(
        oas_type: str,
        prop_key: str,
        prop_value: bool,
) -> None:
    with pytest.raises(exceptions.OASConflict) as err:
        parse_type.resolve(
            components={},
            work_item={
                'allOf': [
                    {
                        'type': oas_type,
                        prop_key: prop_value,
                    },
                    {
                        'type': oas_type,
                        prop_key: not prop_value,
                    },
                ],
            },
        )

    assert (
        f'{prop_key} value differs between mixed schemas. '
        f'a={prop_value} != b={not prop_value}. When using "anyOf,oneOf,allOf" values in '
        f'same location must be equal. '
        f'Either make it so or remove one of the duplicating properties.'
    ) == str(err.value)


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


def test_all_of_any() -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            'allOf': [
                {
                    'default': 10,
                },
                {
                    'default': 10,
                    'example': 'Test',
                },
                {
                    'readOnly': True,
                },
                {
                    'writeOnly': False,
                },
            ],
        },
    )

    assert isinstance(mix_type, model.OASAnyType)
    assert 10 == mix_type.default
    assert 'Test' == mix_type.example

    assert mix_type.read_only
    assert not mix_type.write_only

    assert not mix_type.deprecated


def test_all_of_boolean() -> None:
    mix_type = parse_type.resolve(
        components={},
        work_item={
            'allOf': [
                {
                    'default': True,
                },
                {
                    'default': True,
                    'example': False,
                },
                {
                    'type': 'boolean',
                    'readOnly': True,
                },
                {
                    'deprecated': False,
                },
                {
                    'writeOnly': False,
                },
            ],
        },
    )

    assert isinstance(mix_type, model.OASBooleanType)
    assert mix_type.default
    assert not mix_type.example
    assert mix_type.read_only
    assert not mix_type.write_only
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


def test_all_of_object_ref_properties() -> None:
    mix_type = parse_type.resolve(
        components={
            'schemas': {
                'Weight': {
                    'type': 'number',
                    'example': 15.0,
                    'format': 'kilogram',
                },
                'Mighty': {
                    'type': 'boolean',
                    'example': True,
                },
                'Hammer': {
                    'type': 'object',
                    'required': ['weight'],
                    'properties': {
                        'weight': {
                            '$ref': '#/components/schemas/Weight',
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
                            '$ref': '#/components/schemas/Mighty',
                        },
                        'weight': {
                            '$ref': '#/components/schemas/Weight',
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


@pytest.mark.parametrize(
    'ap_1,ap_2,should_raise',
    (
        (True, True, False),
        (True, False, True),
        (False, False, False),
        (False, True, True),
        (None, True, False),
        (None, False, False),
        (True, None, False),
        (False, None, False),
        (None, None, False),
        (
            True,
            {
                'type': 'number',
            },
            True,
        ),
        (
            {
                '$ref': '#/components/schemas/Power',
            },
            True,
            True,
        ),
        (
            {
                'type': 'string',
            },
            None,
            False,
        ),
        (
            None,
            {
                'type': 'string',
            },
            False,
        ),
        (
            {
                'type': 'string',
            },
            {
                'type': 'string',
            },
            False,
        ),
        (
            {
                '$ref': '#/components/schemas/Power',
            },
            None,
            False,
        ),
        (
            None,
            {
                '$ref': '#/components/schemas/Power',
            },
            False,
        ),
        (
            {
                'type': 'string',
            },
            {
                'type': 'number',
            },
            True,
        ),
        (
            {
                'type': 'string',
            },
            {
                '$ref': '#/components/schemas/Power',
            },
            True,
        ),
        (
            {
                '$ref': '#/components/schemas/Power',
            },
            {
                'type': 'string',
            },
            True,
        ),
        (
            {
                '$ref': '#/components/schemas/Power',
            },
            {
                '$ref': '#/components/schemas/Power',
            },
            False,
        ),
    ),
)
def test_all_of_object_additional_properties(
        should_raise: bool,
        ap_1: t.Optional[t.Union[bool, t.Dict[str, t.Any]]],
        ap_2: t.Optional[t.Union[bool, t.Dict[str, t.Any]]],
) -> None:
    def _do() -> t.Any:
        return parse_type.resolve(
            components={
                'schemas': {
                    'Weight': {
                        'type': 'number',
                        'example': 15.0,
                        'format': 'kilogram',
                    },
                    'Mighty': {
                        'type': 'boolean',
                        'example': True,
                    },
                    'Power': {
                        'type': 'number',
                    },
                    'Hammer': {
                        'type': 'object',
                        'required': ['weight'],
                        'properties': {
                            'weight': {
                                '$ref': '#/components/schemas/Weight',
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
                                '$ref': '#/components/schemas/Mighty',
                            },
                        },
                    },
                    {
                        'additionalProperties': ap_1,
                    },
                    {
                        'additionalProperties': ap_2,
                    },
                ],
            },
        )

    if should_raise:
        with pytest.raises(exceptions.OASConflict) as err:
            _do()
        if isinstance(ap_1, bool) and isinstance(ap_2, bool):
            assert (
                f'additionalProperties value differs between mixed schemas. '
                f'a={ap_1} != b={ap_2}. When using "anyOf,oneOf,allOf" values in '
                f'same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.'
            ) == str(err.value)
        elif isinstance(ap_1, dict) and isinstance(ap_2, dict):
            if 'type' in ap_1 and 'type' in ap_2:
                assert (
                    f'additionalProperties.type value differs between mixed schemas. '
                    f'a={ap_1["type"]} != b={ap_2["type"]}. '
                    f'When using "anyOf,oneOf,allOf" values in '
                    f'same location must be equal. '
                    f'Either make it so or remove one of the duplicating properties.'
                ) == str(err.value)
            elif 'type' in ap_1 and '$ref' in ap_2:
                assert (
                    f'additionalProperties value differs between mixed schemas. '
                    f'One defines inline schema with '
                    f'type={ap_1["type"]} and the other has $ref={ap_2["$ref"]} '
                    f'When using "anyOf,oneOf,allOf" values in '
                    f'same location must be equal. '
                    f'Either make it so or remove one of the duplicating properties.'
                ) == str(err.value)
            elif '$ref' in ap_1 and 'type' in ap_2:
                assert (
                    f'additionalProperties value differs between mixed schemas. '
                    f'One defines inline schema with '
                    f'type={ap_2["type"]} and the other has $ref={ap_1["$ref"]} '
                    f'When using "anyOf,oneOf,allOf" values in '
                    f'same location must be equal. '
                    f'Either make it so or remove one of the duplicating properties.'
                ) == str(err.value)
            else:
                raise AssertionError('This should not happen')
        elif isinstance(ap_1, bool) and isinstance(ap_2, dict):
            assert (
                f'additionalProperties value differs between mixed schemas. '
                f'a=bool != b=dict. When using "anyOf,oneOf,allOf" values in '
                f'same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.'
            ) == str(err.value)
        elif isinstance(ap_1, dict) and isinstance(ap_2, bool):
            assert (
                f'additionalProperties value differs between mixed schemas. '
                f'a=dict != b=bool. When using "anyOf,oneOf,allOf" values in '
                f'same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.'
            ) == str(err.value)
        else:
            raise AssertionError('This should not happen')
    else:
        mix_type = _do()

        assert isinstance(mix_type, model.OASObjectType)
        assert 2 == len(mix_type.properties)

        assert 'weight' in mix_type.properties
        assert isinstance(mix_type.properties['weight'], model.OASNumberType)

        assert 'isMighty' in mix_type.properties
        assert isinstance(mix_type.properties['isMighty'], model.OASBooleanType)

        oas_type_map = {
            'string': model.OASStringType,
            'boolean': model.OASBooleanType,
            'number': model.OASNumberType,
            'integer': model.OASNumberType,
            'object': model.OASObjectType,
            'array': model.OASArrayType,
        }

        if ap_1 is None and ap_2 is None:
            assert mix_type.additional_properties
        elif ap_1 is not None and ap_2 is None:
            if isinstance(ap_1, bool):
                assert ap_1 == mix_type.additional_properties
            elif 'type' in ap_1:
                assert isinstance(
                    mix_type.additional_properties,
                    oas_type_map[ap_1['type']],
                )
            elif '$ref' in ap_1:
                assert isinstance(
                    mix_type.additional_properties,
                    model.OASNumberType,
                )
            else:
                raise AssertionError('This should not happen')
        elif ap_1 is None and ap_2 is not None:
            if isinstance(ap_2, bool):
                assert ap_2 == mix_type.additional_properties
            elif 'type' in ap_2:
                assert isinstance(
                    mix_type.additional_properties,
                    oas_type_map[ap_2['type']],
                )
            elif '$ref' in ap_2:
                assert isinstance(
                    mix_type.additional_properties,
                    model.OASNumberType,
                )
            else:
                raise AssertionError('This should not happen')
        elif ap_1 is not None and ap_2 is not None:
            if isinstance(ap_1, bool) and isinstance(ap_2, bool):
                assert ap_1 == ap_2 == mix_type.additional_properties
            elif isinstance(ap_1, dict) and isinstance(ap_2, dict):
                if 'type' in ap_1 and 'type' in ap_2:
                    assert oas_type_map[ap_1['type']] == oas_type_map[ap_2['type']]
                    assert isinstance(
                        mix_type.additional_properties,
                        oas_type_map[ap_2['type']],
                    )
                elif '$ref' in ap_1 and '$ref' in ap_2:
                    assert '#/components/schemas/Power' == ap_1['$ref'] == ap_2['$ref']
                else:
                    raise AssertionError('This should not happen')
            else:
                raise AssertionError('This should not happen')
        else:
            raise AssertionError('This should not happen')


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
