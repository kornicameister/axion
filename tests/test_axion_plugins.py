import axion


def test_builtin_plugins_detected() -> None:
    assert len(axion._plugins()) == 1
    assert 'aiohttp' in axion._plugins()
    assert 1 == len(getattr(axion._plugins, '__cache__', []))
