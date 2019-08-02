def test_import_application_from_root_pkg() -> None:
    try:
        from axion import Application
    except ImportError:
        raise AssertionError('axion.Application not importable from main package')
