from pathlib import Path
import typing as t

from loguru import logger
import typing_extensions as te

from axion import app
from axion import oas

Application = app.Application

if t.TYPE_CHECKING:
    from axion import plugin
    PluginId = plugin.PluginId
    Plugin = plugin.Plugin
else:
    PluginId = Plugin = None


@te.final
class Axion:
    __slots__ = 'root_dir', 'plugin_id'

    def __init__(
            self,
            root_dir: Path,
            plugin_id: PluginId,
    ) -> None:
        self.root_dir = root_dir
        self.plugin_id = plugin_id

    def add_api(
            self,
            spec_location: Path,
            server_base_path: t.Optional[str] = None,
            *_: None,
            **kwargs: t.Any,
    ) -> None:

        if not spec_location.is_absolute():
            spec_location = (self.root_dir / spec_location).resolve().absolute()

        self.plugged.add_api(oas.load(spec_location), server_base_path, **kwargs)


def _plugins() -> t.Mapping[PluginId, t.Type[Plugin]]:
    discovered_plugins: t.Optional[t.Mapping[PluginId, t.Type[Plugin]]] = getattr(
        _plugins,
        '__cache__',
        None,
    )

    logger.opt(
        record=True,
        lazy=True,
    ).debug(
        '_plugins cache status is {s}=>{c}',
        s=lambda: 'ON' if discovered_plugins else 'OFF',
        c=lambda: len(discovered_plugins or {}),
    )

    if not discovered_plugins:
        import importlib
        import inspect
        import pkgutil
        import types

        def iter_ns(import_name: str) -> t.Generator[pkgutil.ModuleInfo, None, None]:
            ns_pkg: types.ModuleType = importlib.import_module(import_name)
            return pkgutil.iter_modules(
                ns_pkg.__dict__['__path__'],
                f'{ns_pkg.__name__}.',
            )

        def to_plugin(
                maybe_plugin: t.Optional[t.Any] = None,
        ) -> t.Optional[t.Type[Plugin]]:
            if not maybe_plugin:
                return None
            elif not issubclass(maybe_plugin, plugin.Plugin):
                return None
            else:
                return t.cast(t.Type[Plugin], maybe_plugin)

        def check_and_get(m: t.Any) -> t.Tuple[PluginId, t.Type[Plugin]]:
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
            p = t.cast(t.Type[Plugin], plugin_classes[0])
            return p.plugin_info().id, p

        discovered_plugins = dict([
            check_and_get(importlib.import_module(name))
            for __, name, __ in iter_ns('axion.plugins')
        ])

        setattr(_plugins, '__cache__', discovered_plugins)  # noqa

    return discovered_plugins
