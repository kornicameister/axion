from pathlib import Path
from typing import (Any, cast, Generator, Mapping, Optional, Tuple, Type, Union)

from loguru import logger
from typing_extensions import (final)

from axion.conf import (Configuration)
from axion.oas import (
    load as load_specification,
    oas_endpoint,
)
from axion.plugin import (Plugin, PluginId)

Plugins = Mapping[PluginId, Type[Plugin]]

__all__ = (
    'Axion',
    'Configuration',
    'oas_endpoint',
)


@final
class Axion:
    __slots__ = (
        'root_dir',
        'plugin_id',
        'plugged',
    )

    def __init__(
        self,
        root_dir: Path,
        plugin_id: Union[PluginId, str],
        configuration: Configuration,
        *_: None,
        **kwargs: Any,
    ) -> None:
        self.root_dir = root_dir
        self.plugin_id = plugin_id

        self.plugged = _plugins()[PluginId(plugin_id)](
            configuration,
            **kwargs,
        )

    def add_api(
        self,
        spec_location: Path,
        server_base_path: Optional[str] = None,
        *_: None,
        **kwargs: Any,
    ) -> None:

        if not spec_location.is_absolute():
            spec_location = (self.root_dir / spec_location).resolve().absolute()

        spec = load_specification(spec_location)

        self.plugged.add_api(
            spec=spec,
            base_path=server_base_path,
            **kwargs,
        )

    def __repr__(self) -> str:
        return f'axion running {self.plugin_id} application'


def _plugins() -> Plugins:
    discovered_plugins: Plugins = getattr(
        _plugins,
        '__cache__',
        None,
    )

    logger.opt(lazy=True).debug(
        '_plugins cache status is {s}=>{c}',
        s=lambda: 'ON' if discovered_plugins else 'OFF',
        c=lambda: len(discovered_plugins or {}),
    )

    if not discovered_plugins:
        import importlib
        import inspect
        import pkgutil
        import types

        def iter_ns(import_name: str) -> Generator[pkgutil.ModuleInfo, None, None]:
            ns_pkg: types.ModuleType = importlib.import_module(import_name)
            return pkgutil.iter_modules(
                ns_pkg.__dict__['__path__'],
                f'{ns_pkg.__name__}.',
            )

        def to_plugin(maybe_plugin: Optional[Any] = None) -> Optional[Type[Plugin]]:
            if not maybe_plugin:
                return None
            elif not issubclass(maybe_plugin, Plugin):
                return None
            else:
                return cast(Type[Plugin], maybe_plugin)

        def check_and_get(m: Any) -> Tuple[PluginId, Type[Plugin]]:
            classes = (getattr(m, el) for el in dir(m) if inspect.isclass(getattr(m, el)))
            plugin_classes = list(
                filter(
                    lambda p: p is not None,
                    map(to_plugin, classes),
                ),
            )
            assert len(
                plugin_classes,
            ) == 1, f'Builtin plugin module {m.__name__} should define just one plugin'
            p = cast(Type[Plugin], plugin_classes[0])
            return p.plugin_info().id, p

        discovered_plugins = dict([
            check_and_get(importlib.import_module(name))
            for __, name, __ in iter_ns('axion.plugins')
        ])

        setattr(_plugins, '__cache__', discovered_plugins)  # noqa

    return discovered_plugins
