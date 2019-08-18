import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import parser


@pytest.mark.parametrize('default', [1, bool, {}, []])
def test_spec_build_oas_string_default_wrong_type(default: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_string({'default': default})


@pytest.mark.parametrize('example', [1, bool, {}, []])
def test_spec_build_oas_string_example_wrong_type(example: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_string({'example': example})


@pytest.mark.parametrize(('min_length', 'max_length'), [(2, 1), (10, 1)])
def test_spec_build_oas_string_invalid_min_max_length(
        min_length: int,
        max_length: int,
) -> None:
    with pytest.raises(exceptions.OASInvalidConstraints):
        parser._build_oas_string({
            'minLength': min_length,
            'maxLength': max_length,
        })
