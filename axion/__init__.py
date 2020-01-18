from pathlib import Path
import typing as t

from loguru import logger
import typing_extensions as te

from axion import app
from axion import oas
from axion import plugin

Application = app.Application

LOG: te.Final = logger.opt(record=True, lazy=True)


@te.final
class Axion:
    __slots__ = 'root_dir', 'plugged'

    def __init__(
            self,
            root_dir: Path,
            # TODO(kornicameister) this should be plugin ID
            plugged: plugin.Plugin,
    ) -> None:
        self.root_dir = root_dir
        self.plugged = plugged

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


def plugins() -> t.Tuple[plugin.Plugin, ...]:
    import importlib
    import inspect
    import pkgutil

    import axion.plugins

    def iter_ns(ns_pkg: t.Any) -> t.Generator[pkgutil.ModuleInfo, None, None]:
        return pkgutil.iter_modules(ns_pkg.__path__, f'{ns_pkg.__name__}.')

    def to_plugin(maybe_plugin: t.Type[t.Any]) -> t.Optional[t.Type[plugin.Plugin]]:
        if not issubclass(maybe_plugin, plugin.Plugin):
            return None
        else:
            return maybe_plugin

    def check(m: t.Any) -> plugin.Plugin:
        classes = (getattr(m, el) for el in dir(m) if inspect.isclass(getattr(m, el)))
        plugin_classes = list(filter(lambda p: p is not None, map(to_plugin, classes)))
        assert len(
            plugin_classes,
        ) == 1, f'Builtin plugin module {m.__name__} should define just one plugin'
        return t.cast(plugin.Plugin, plugin_classes[0])

    with LOG.contextualize(plugins='builtin'):
        discovered_plugins = [
            check(importlib.import_module(name))
            for __, name, __ in iter_ns(axion.plugins)
        ]
        LOG.info('Found {c} plugins', c=lambda: len(discovered_plugins))

    return tuple(discovered_plugins)
