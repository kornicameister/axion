import pytest

from axion import plugin


def test_subclass_ok() -> None:
    class P1(plugin.Plugin, version='0.0.1'):
        """P1 plugin"""

    class P2(plugin.Plugin, version='0.0.3'):
        """P2 plugin"""

    p1_info = P1.plugin_info()
    p2_info = P2.plugin_info()

    assert p1_info
    assert p2_info

    assert p1_info != p2_info

    assert p1_info.name == 'P1'
    assert p1_info.version == (0, 0, 1)
    assert p1_info.documentation == 'P1 plugin'

    assert p2_info.name == 'P2'
    assert p2_info.version == (0, 0, 3)
    assert p2_info.documentation == 'P2 plugin'


def test_no_double_subclass() -> None:
    class P1(plugin.Plugin, version='0.0.1'):
        """P1 plugin"""

    with pytest.raises(TypeError):

        class P2(P1, version='0.0.3'):
            """P1 plugin should not be subclassed"""
