import typing as t

import pytest

from axion.specification.parser import type as parse_type


@pytest.mark.parametrize('python_type', (str, int, float, dict, set, list, bool))
def test_python_type(python_type: t.Type[t.Any]) -> None:
    assert issubclass(
        python_type,
        parse_type._build_oas_any({}).python_type,
    )
