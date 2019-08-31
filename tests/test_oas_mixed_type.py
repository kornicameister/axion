import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import model
from axion.specification.parser import type as parse_type


@pytest.mark.parametrize(
    'mix_key,mix_kind',
    (
        ('oneOf', model.OASOneOfType),
        ('allOf', model.OASAllOfType),
        ('anyOf', model.OASAnyOfType),
    ),
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
def test_build(
        mix_key: str,
        mix_kind: t.Type[t.Union[model.OASAnyOfType,
                                 model.OASAllOfType,
                                 model.OASOneOfType,
                                 ],
                         ],
        in_mix: t.List[t.Dict[str, t.Any]],
        expected_schemas: t.List[t.Tuple[bool, t.Type[model.OASType[t.Any]]]],
) -> None:
    mix_type = parse_type._build_oas_mix(
        components={},
        work_item={
            mix_key: in_mix,
        },
    )

    assert isinstance(mix_type, model.OASMixedType)
    assert isinstance(mix_type.mix, mix_kind)
    assert len(mix_type.schemas) == len(in_mix)
    assert list(
        map(
            lambda v: (v[0], type(v[1])),
            mix_type.schemas,
        ),
    ) == expected_schemas


def test_any_of_all_types_is_oas_any() -> None:
    mix_type = parse_type._build_oas_mix(
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


def test_all_of_impossible() -> None:
    with pytest.raises(exceptions.OASConflict):
        ...
