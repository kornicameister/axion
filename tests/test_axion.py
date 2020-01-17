import axion


def test_builtin_plugins_detected() -> None:
    assert len(axion.plugins()) == 1
