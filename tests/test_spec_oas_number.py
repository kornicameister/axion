import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import parser


@pytest.mark.parametrize('key', ('default', 'example', 'minimum', 'maximum'))
@pytest.mark.parametrize('value', ['1', bool, {}, []])
def test_spec_build_oas_number_wrong_value_type(key: str, value: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_number({key: value})


@pytest.mark.parametrize(
    ('example', 'default'),
    (
        (0, 1.0),
        (1.0, 0),
    ),
)
def test_spec_build_oas_number_mismatch_example_default(
        example: t.Any,
        default: t.Any,
) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_number({
            'example': example,
            'default': default,
        })
