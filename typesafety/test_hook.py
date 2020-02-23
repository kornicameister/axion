from pathlib import Path

from pytest_mypy.item import YamlTestItem


def hook(test_item: YamlTestItem) -> None:
    axion_dir = Path(test_item.base_ini_fpath).parents[1]

    plugin_path = (axion_dir / 'axion' / 'oas_mypy' / '__init__.py').resolve()
    oas_specifications_path = Path.cwd().resolve()

    oas_spec = test_item.parsed_test_data.get('oas_spec', None)
    if oas_spec:
        spec_path = Path(oas_specifications_path / f'{test_item.name}.spec.yml')
        with spec_path.open('w') as handler:
            handler.write(oas_spec)

    additional_mypy_config = """
        [mypy]
        plugins = {plugin_path}
        [axion-mypy]
        oas_directories = {oas_specifications_path}
    """.format(
        plugin_path=plugin_path,
        oas_specifications_path=oas_specifications_path,
    )
    test_item.additional_mypy_config = additional_mypy_config
