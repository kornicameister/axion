import typing as t

from loguru import logger
import typing_extensions as te

from axion import app
from axion import plugin

Application = app.Application

LOG: te.Final = logger.opt(record=True, lazy=True)


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
