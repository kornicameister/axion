import pytest

from axion import application


def normal_f() -> None:
    ...


async def async_f() -> None:
    ...


def test_resolve_handler_module_not_found() -> None:
    with pytest.raises(application.InvalidHandlerError) as err:
        application.resolve_handler('really_dummy.api.get_all')
    assert err.match('Failed to import module=really_dummy.api')


def test_resolve_handler_function_not_found() -> None:
    with pytest.raises(application.InvalidHandlerError) as err:
        application.resolve_handler('tests.test_application_handler.foo')
    assert err.match(
        'Failed to locate function=foo in module=tests.test_application_handler',
    )


def test_resolve_handler_not_couroutine() -> None:
    with pytest.raises(application.InvalidHandlerError) as err:
        application.resolve_handler('tests.test_application_handler.normal_f')
    assert err.match(
        'tests.test_application_handler.normal_f did not resolve to coroutine',
    )


def test_resolve_handler_couroutine() -> None:
    handler = application.resolve_handler('tests.test_application_handler.async_f')
    assert handler is async_f
