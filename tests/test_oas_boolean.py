import typing as t

import pytest

from axion.oas import exceptions
from axion.oas.parser import type as parse_type


@pytest.mark.parametrize('key', ('default', 'example'))
@pytest.mark.parametrize('value', ['1', 1, {}, []])
def test_wrong_value_type(key: str, value: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parse_type.resolve(
            {},
            {
                'type': 'boolean',
                key: value,
            },
        )


def test_python_type() -> None:
    assert issubclass(parse_type.resolve(
        {},
        {
            'type': 'boolean',
        },
    ).python_type, bool)


def test_oas_type() -> None:
    assert parse_type.resolve({}, {'type': 'boolean'}).oas_type == 'boolean'
