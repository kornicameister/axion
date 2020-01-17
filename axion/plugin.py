import typing as t


class PluginMeta(type):
    def __new__(
            cls,
            name: t.Any,
            bases: t.Any,
            dct: t.Any,
            version: t.Optional[str] = None,
    ) -> t.Any:
        p = super().__new__(cls, name, bases, dct)

        if name == 'Plugin' and dct['__module__'] == __name__:
            return p

        def _no_subclassing_of_plugin() -> None:
            parent_name = f'{dct["__module__"]}.{dct["__qualname__"]}'
            raise TypeError(f'Inheriting from {parent_name} is forbidden.')

        plugin_name = name
        plugin_version = tuple(map(int, (version or '').split('.')))
        plugin_docs = dct.pop('__doc__', None)

        # make sure that plugin is a correct subclass
        assert plugin_name, 'Plugin must present a version'
        assert plugin_version, 'Plugin must present SemVer version'
        assert plugin_docs, 'Plugin must present documentation'

        # disallow further subclassing
        setattr(  # noqa
            p,
            '__init_subclass__',
            _no_subclassing_of_plugin,
        )

        # add some metadata
        setattr(  # noqa
            p,
            'plugin_info',
            lambda: PluginInfo(
                name=plugin_name,
                version=plugin_version,
                documentation=plugin_docs,
            ),
        )

        return p


class Plugin(metaclass=PluginMeta):
    plugin_info: t.ClassVar[t.Callable[[], 'PluginInfo']]


class PluginInfo(t.NamedTuple):
    name: str
    version: t.Tuple[int, ...]
    documentation: str
