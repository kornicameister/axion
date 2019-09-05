import typing as t

import pytest

from axion.specification import exceptions
from axion.specification.parser import type as parse_type


@pytest.mark.parametrize(
    'oas_type,number_cls',
    (('integer', int), ('number', float)),
)
def test_python_type(
        oas_type: str,
        number_cls: t.Type[t.Union[int, float]],
) -> None:
    assert issubclass(
        parse_type.resolve(
            components={},
            work_item={
                'type': oas_type,
            },
        ).python_type,
        number_cls,
    )


@pytest.mark.parametrize('oas_type', ('number', 'integer'))
@pytest.mark.parametrize('key', ('default', 'example', 'minimum', 'maximum'))
@pytest.mark.parametrize('value', ['1', bool, {}, []])
def test_wrong_value_type(
        oas_type: str,
        key: str,
        value: t.Any,
) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parse_type.resolve({}, {'type': oas_type, key: value})


@pytest.mark.parametrize(
    ('example', 'default'),
    (
        (0, 1.0),
        (1.0, 0),
    ),
)
def test_mismatch_example_default(
        example: t.Any,
        default: t.Any,
) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parse_type.resolve(
            {},
            {
                'type': 'integer',
                'example': example,
                'default': default,
            },
        )
