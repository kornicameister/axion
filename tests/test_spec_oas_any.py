import typing as t

import pytest

from axion.specification import parser


@pytest.mark.parametrize('python_type', (str, int, float, dict, set, list, bool))
def test_spec_build_oas_any_python_type(python_type: t.Type[t.Any]) -> None:
    assert issubclass(
        python_type,
        parser._build_oas_any({}).python_type,
    )
