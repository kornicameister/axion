import types
import typing as t

import pytest

from axion import plugin


@pytest.mark.parametrize(
    'meta_dict,expected_err',
    (
        (
            {
                'id': 'plugin',
            },
            'Plugin must present a version',
        ),
        (
            {
                'version': '0.0.1',
            },
            'Plugin must present an ID',
        ),
    ),
)
def test_missing_plugin_meta(
    meta_dict: t.Dict[str, str],
    expected_err: str,
) -> None:
    with pytest.raises(plugin.InvalidPluginDefinition) as err:

        def exec_body(ns: t.Dict[str, t.Any]) -> None:
            ns['__doc__'] = test_missing_plugin_meta.__name__

        types.new_class(
            'PluginThatMissesThings',
            (plugin.Plugin, ),
            meta_dict,
            exec_body,
        )

    assert err.value
    assert str(err.value) == expected_err


def test_missing_doc() -> None:
    with pytest.raises(plugin.InvalidPluginDefinition) as err:

        class NoDoc(plugin.Plugin, id='noDoc', version='0.0.1'):
            ...

    assert err.value
    assert str(err.value) == 'Plugin must present documentation'


def test_subclass_ok() -> None:
    class P1(plugin.Plugin, id='p1', version='0.0.1'):
        """P1 plugin"""

    class P2(plugin.Plugin, id='p2', version='0.0.3'):
        """P2 plugin"""

    p1_info = P1.plugin_info()
    p2_info = P2.plugin_info()

    assert p1_info
    assert p2_info

    assert p1_info != p2_info

    assert p1_info.id == 'p1'
    assert p1_info.name == 'P1'
    assert p1_info.version == (0, 0, 1)
    assert p1_info.documentation == 'P1 plugin'

    assert p2_info.id == 'p2'
    assert p2_info.name == 'P2'
    assert p2_info.version == (0, 0, 3)
    assert p2_info.documentation == 'P2 plugin'


def test_no_double_subclass() -> None:
    class P1(plugin.Plugin, id='p3', version='0.0.1'):
        """P1 plugin"""

    with pytest.raises(TypeError):

        class P2(P1, id='p2', version='0.0.3'):
            """P1 plugin should not be subclassed"""


def test_no_plugin_duplication() -> None:
    bad_id = 'thor'

    class P1(plugin.Plugin, id=bad_id, version='0.0.1'):
        """P1 plugin"""

    with pytest.raises(plugin.InvalidPluginDefinition) as err:

        class P2(plugin.Plugin, id=bad_id, version='0.0.1'):
            """P2 plugin"""

    assert str(
        err.value,
    ) == f'Plugin with ID={bad_id} is already registered as {P1.__qualname__}'


def test_bad_init_extra_arg() -> None:
    from axion import conf

    with pytest.raises(plugin.InvalidPluginDefinition) as err:

        class BadInit(plugin.Plugin, id='BadInit', version='0.0.1'):
            """I am naughty to try and have config of bad type __init___"""
            def __init__(self, is_debug: bool, cfg: t.Dict[str, str]) -> None:
                super().__init__(cfg)  # type: ignore

    assert err.value
    assert str(err.value) == (
        f'Plugin with ID=BadInit has incorrect __init__ signature. '
        f'It should accept an argument either '
        f'of {repr(conf.Configuration)} type or called "configuration"'
    )


def test_good_inits() -> None:
    from axion import conf

    class GoodInit_1(plugin.Plugin, id='g1', version='0.0.1'):
        """I am wonderful"""
        def __init__(self, cfg: conf.Configuration) -> None:
            super().__init__(cfg)

    class GoodInit_2(plugin.Plugin, id='g2', version='0.0.1'):
        """I am wonderful"""

    class GoodInit_3(plugin.Plugin, id='g3', version='0.0.2'):
        """The configuration named arguments."""
        def __init__(self, configuration: t.Dict[str, t.Any]) -> None:
            self.cfg = configuration
