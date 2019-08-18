import typing as t

import pytest

from axion.specification import exceptions
from axion.specification import parser


@pytest.mark.parametrize('key', ('default', 'example'))
@pytest.mark.parametrize('value', ['1', 1, {}, []])
def test_spec_build_oas_boolean_wrong_value_type(key: str, value: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        parser._build_oas_boolean({key: value})
