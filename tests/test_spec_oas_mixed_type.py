import typing as t

import pytest

from axion.specification import model
from axion.specification import parser


@pytest.mark.parametrize(
    'mix_key,mix_kind',
    (
        ('oneOf', model.OASMixedType.Kind.EITHER),
        ('allOf', model.OASMixedType.Kind.UNION),
        ('anyOf', model.OASMixedType.Kind.ANY),
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
def test_oas_mixed_type_build(
        mix_key: str,
        mix_kind: model.OASMixedType.Kind,
        in_mix: t.List[t.Dict[str, t.Any]],
        expected_schemas: t.List[t.Tuple[bool, t.Type[model.OASType[t.Any]]]],
) -> None:
    mix_type = parser._build_oas_mix(
        components={},
        work_item={
            mix_key: in_mix,
        },
    )

    assert mix_type.kind == mix_kind
    assert len(mix_type.sub_schemas) == len(in_mix)
    assert list(
        map(
            lambda v: (v[0], type(v[1])),
            mix_type.sub_schemas,
        ),
    ) == expected_schemas
