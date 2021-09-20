import typing as t

import pytest

from axion.oas import exceptions
from axion.oas import model
from axion.oas.parser import type as parse_type


def test_oas_type() -> None:
    assert parse_type.resolve({}, {'type': 'string'}).oas_type == 'string'


def test_correct_python_type() -> None:
    oas_string = parse_type.resolve(
        {},
        {
            'type': 'string',
        },
    )

    assert isinstance(oas_string, model.OASStringType)
    assert issubclass(oas_string.python_type, str)


@pytest.mark.parametrize('default', [1, bool, {}, []])
def test_default_wrong_type(default: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parse_type.resolve(
            {},
            {
                'type': 'string',
                'default': default,
            },
        )


@pytest.mark.parametrize('example', [1, bool, {}, []])
def test_example_wrong_type(example: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parse_type.resolve(
            {},
            {
                'type': 'string',
                'example': example,
            },
        )


@pytest.mark.parametrize(('min_length', 'max_length'), [(2, 1), (10, 1)])
def test_invalid_min_max_length(
    min_length: int,
    max_length: int,
) -> None:
    with pytest.raises(exceptions.OASInvalidConstraints):
        parse_type.resolve(
            {},
            {
                'type': 'string',
                'minLength': min_length,
                'maxLength': max_length,
            },
        )


@pytest.mark.parametrize(
    'pattern,should_match,should_not_match',
    (
        ('^[a-z]*$', ['a', 'ab', 'abc'], ['123', '456']),
        ('^[a-z0-9_-]{3,16}$', ['my-us3r_n4m3'], ['th1s1s-wayt00_l0ngt0beausername']),
    ),
)
def test_pattern(
    pattern: str,
    should_match: t.List[str],
    should_not_match: t.List[str],
) -> None:
    oas_string = parse_type.resolve(
        {},
        {
            'type': 'string',
            'pattern': pattern,
        },
    )
    assert isinstance(oas_string, model.OASStringType)
    assert oas_string.pattern is not None
    for example in should_match:
        assert oas_string.pattern.match(example) is not None, f'{pattern} did not match'
    for example in should_not_match:
        assert oas_string.pattern.match(example) is None, f'{pattern} did match'
