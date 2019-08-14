import typing as t

import pytest

from axion import spec
from axion.spec import exceptions


@pytest.mark.parametrize('key', ('default', 'example'))
@pytest.mark.parametrize('value', ['1', 1, {}, []])
def test_spec_build_oas_boolean_wrong_value_type(key: str, value: t.Any) -> None:
    with pytest.raises(exceptions.OASInvalidTypeValue):
        spec._build_oas_boolean({key: value})
