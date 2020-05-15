import typing as t

import pytest

from axion.oas import exceptions
from axion.oas import model
from axion.oas.parser import type as parse_type


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


@pytest.mark.parametrize('mix_key', ('oneOf', 'anyOf'))
@pytest.mark.parametrize(
    'weapon_discriminator,mix_discriminator',
    (
        (None, None),
        (
            None,
            {
                'discriminator': {
                    'propertyName': 'kind',
                    'mapping': {
                        'hammer': 'Hammer',
                        'gun': 'Gun',
                    },
                },
            },
        ),
        (
            {
                'discriminator': {
                    'propertyName': 'kind',
                    'mapping': {
                        'hammer': 'Hammer',
                        'gun': 'Gun',
                    },
                },
            },
            None,
        ),
    ),
)
def test_one_any_of_discriminator(
    mix_key: str,
    weapon_discriminator: t.Optional[t.Dict[str, t.Any]],
    mix_discriminator: t.Optional[t.Dict[str, t.Any]],
) -> None:
    mix_type = parse_type.resolve(
        components={
            'schemas': {
                'Weapon': {
                    **(weapon_discriminator or {}),
                    **{
                        'type': 'object',
                        'required': ['weight', 'kind'],
                        'properties': {
                            'weight': {
                                'type': 'number',
                            },
                            'kind': {
                                'type': 'string',
                            },
                        },
                    },
                },
                'Gun': {
                    'allOf': [
                        {
                            '$ref': '#/components/schemas/Weapon',
                        },
                        {
                            'type': 'object',
                            'required': ['ammoCount'],
                            'properties': {
                                'ammoCount': {
                                    'type': 'integer',
                                },
                            },
                        },
                    ],
                },
                'Hammer': {
                    'allOf': [
                        {
                            '$ref': '#/components/schemas/Weapon',
                        },
                        {
                            'type': 'object',
                            'required': ['material'],
                            'properties': {
                                'material': {
                                    'type': 'string',
                                    'enum': ['wood', 'steal', 'bronze', 'silver'],
                                },
                            },
                        },
                    ],
                },
            },
        },
        work_item={
            **(mix_discriminator or {}),
            **{
                mix_key: [
                    {
                        '$ref': '#/components/schemas/Hammer',
                    },
                    {
                        '$ref': '#/components/schemas/Gun',
                    },
                ],
            },
        },
    )

    assert isinstance(mix_type, (model.OASAnyOfType, model.OASOneOfType))

    discriminator_def = ((mix_discriminator or weapon_discriminator) or {})
    if discriminator_def:
        assert mix_type.discriminator
        assert 'kind' == mix_type.discriminator.property_name
        assert discriminator_def['discriminator']['mapping'
                                                  ] == mix_type.discriminator.mapping
    else:
        assert not mix_type.discriminator


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
                'additionalProperties value differs between mixed schemas. '
                'a=bool != b=dict. When using "anyOf,oneOf,allOf" values in '
                'same location must be equal. '
                'Either make it so or remove one of the duplicating properties.'
            ) == str(err.value)
        elif isinstance(ap_1, dict) and isinstance(ap_2, bool):
            assert (
                'additionalProperties value differs between mixed schemas. '
                'a=dict != b=bool. When using "anyOf,oneOf,allOf" values in '
                'same location must be equal. '
                'Either make it so or remove one of the duplicating properties.'
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


@pytest.mark.parametrize(
    'p_1,p_2,should_raise',
    (
        (
            {
                'discriminator': {
                    'propertyName': 'petType',
                },
            },
            {
                'discriminator': {
                    'propertyName': 'petType',
                },
            },
            False,
        ),
        (
            {
                'discriminator': {
                    'propertyName': 'petType',
                },
            },
            {
                'discriminator': {
                    'propertyName': 'somethingElse',
                },
            },
            True,
        ),
        (
            {
                'discriminator': {
                    'propertyName': 'petType',
                },
            },
            None,
            False,
        ),
        (
            None,
            {
                'discriminator': {
                    'propertyName': 'petType',
                },
            },
            False,
        ),
        (
            None,
            None,
            False,
        ),
    ),
)
def test_all_of_object_discriminator_prop_name(
    p_1: t.Optional[t.Dict[str, t.Any]],
    p_2: t.Optional[t.Dict[str, t.Any]],
    should_raise: bool,
) -> None:
    def _do() -> t.Any:
        return parse_type.resolve(
            components={
                'schemas': {
                    'Pet': {
                        **(p_1 or {}),
                        **{
                            'type': 'object',
                            'properties': {
                                'name': {
                                    'type': 'string',
                                },
                                'petType': {
                                    'type': 'string',
                                },
                            },
                            'required': ['name', 'petType'],
                        },
                    },
                },
            },
            work_item={
                'allOf': [
                    {
                        '$ref': '#/components/schemas/Pet',
                    },
                    {
                        **(p_2 or {}),
                        **{
                            'properties': {
                                'packSize': {
                                    'type': 'integer',
                                    'format': 'int32',
                                    'description': 'the size of the pack the dog is from',
                                    'default': 0,
                                    'minimum': 0,
                                },
                            },
                            'required': [
                                'packSize',
                            ],
                        },
                    },
                ],
            },
        )

    if should_raise:
        with pytest.raises(exceptions.OASConflict) as err:
            _do()
        if p_1 and p_2:
            assert (
                f'discriminator.propertyName value differs between mixed schemas. '
                f'a={p_1["discriminator"]["propertyName"]} '
                f'!= b={p_2["discriminator"]["propertyName"]}. '
                f'When using "anyOf,oneOf,allOf" values in '
                f'same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.'
            ) == str(err.value)
        else:
            raise AssertionError('This should not happen')
    else:
        mix_type = _do()

        assert isinstance(mix_type, model.OASObjectType)
        assert 3 == len(mix_type.properties)

        assert 'name' in mix_type.properties
        assert isinstance(mix_type.properties['name'], model.OASStringType)

        assert 'petType' in mix_type.properties
        assert isinstance(mix_type.properties['petType'], model.OASStringType)

        assert 'packSize' in mix_type.properties
        assert isinstance(mix_type.properties['packSize'], model.OASNumberType)
        assert issubclass(mix_type.properties['packSize'].number_cls, int)

        discriminator = (p_1 or p_2) or {}
        if discriminator:
            assert mix_type.discriminator
            assert mix_type.discriminator.property_name == 'petType'
        else:
            assert mix_type.discriminator is None


@pytest.mark.parametrize(
    'm_1,m_2,should_raise',
    (
        (None, None, False),
        ({}, {}, False),
        ({}, None, False),
        (None, {}, False),
        (
            {
                'dog': 'Dog',
            },
            None,
            False,
        ),
        (
            None,
            {
                'dog': 'Dog',
            },
            False,
        ),
        (
            {
                'dog': 'Dog',
            },
            {
                'dog': 'Dog',
            },
            False,
        ),
        (
            {
                'dog': 'Dog',
                'cat': 'Cat',
            },
            {
                'dog': 'Dog',
                'cat': 'Cat',
            },
            False,
        ),
        (
            {
                'dog': '#/components/schemas/Dog',
            },
            {
                'dog': '#/components/schemas/Dog',
            },
            False,
        ),
        (
            {
                'dog': '#/components/schemas/Dog',
            },
            {
                'dog': '#/components/schemas/Dog',
                'cat': '#/components/schemas/Cat',
            },
            False,
        ),
        (
            {
                'dog': '#/components/schemas/Dog',
            },
            {
                'dog': '#/components/schemas/Husky',
            },
            True,
        ),
    ),
)
def test_all_of_object_discriminator_mapping(
    m_1: t.Optional[t.Dict[str, t.Any]],
    m_2: t.Optional[t.Dict[str, t.Any]],
    should_raise: bool,
) -> None:
    def _do() -> t.Any:
        return parse_type.resolve(
            components={
                'schemas': {
                    'Dog': {
                        'type': 'object',
                        'properties': {
                            'bark': {
                                'type': 'string',
                            },
                        },
                    },
                    'Cat': {
                        'type': 'object',
                        'properties': {
                            'mew': {
                                'type': 'string',
                            },
                        },
                    },
                    'Pet': {
                        'type': 'object',
                        'properties': {
                            'name': {
                                'type': 'string',
                            },
                            'petType': {
                                'type': 'string',
                            },
                        },
                        'required': ['name', 'petType'],
                        'discriminator': {
                            'propertyName': 'petType',
                            'mapping': m_1,
                        },
                    },
                },
            },
            work_item={
                'allOf': [
                    {
                        '$ref': '#/components/schemas/Pet',
                    },
                    {
                        'properties': {
                            'bark': {
                                'type': 'string',
                            },
                        },
                        'discriminator': {
                            'propertyName': 'petType',
                            'mapping': m_2,
                        },
                    },
                ],
            },
        )

    if should_raise:
        with pytest.raises(exceptions.OASConflict) as err:
            _do()
        assert (
            'discriminator.mapping["dog"] value differs between mixed schemas. '
            'a=#/components/schemas/Dog != b=#/components/schemas/Husky. '
            'When using "anyOf,oneOf,allOf" values in same location must '
            'be equal. Either make it so or remove one of the duplicating properties.'
        ) == str(err.value)
    else:
        mix_type = _do()

        assert isinstance(mix_type, model.OASObjectType)
        assert 3 == len(mix_type.properties)

        assert 'name' in mix_type.properties
        assert isinstance(mix_type.properties['name'], model.OASStringType)

        assert 'petType' in mix_type.properties
        assert isinstance(mix_type.properties['petType'], model.OASStringType)

        assert 'bark' in mix_type.properties
        assert isinstance(mix_type.properties['bark'], model.OASStringType)

        assert mix_type.discriminator
        assert mix_type.discriminator.property_name == 'petType'

        mapping = {}
        mapping.update(m_1 or {})
        mapping.update(m_2 or {})

        if mapping:
            assert mapping == mix_type.discriminator.mapping
        else:
            assert not mix_type.discriminator.mapping


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
