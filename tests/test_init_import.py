def test_import_application_from_root_pkg() -> None:
    try:
        from axion import Axion
    except ImportError:
        raise AssertionError('axion.Axion not importable from main package')
