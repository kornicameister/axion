import typing as t

from axion import oas


class PluginMeta(type):
    def __new__(
            cls,
            name: t.Any,
            bases: t.Any,
            dct: t.Any,
            id: t.Optional[str] = None,
            version: t.Optional[str] = None,
    ) -> t.Any:
        p = super().__new__(cls, name, bases, dct)

        if name == 'Plugin' and dct['__module__'] == __name__:
            return p

        def _no_subclassing_of_plugin() -> None:
            parent_name = f'{dct["__module__"]}.{dct["__qualname__"]}'
            raise TypeError(f'Inheriting from {parent_name} is forbidden.')

        plugin_name = str(name)

        try:
            # user-set attributes that axion needs
            plugin_id = str(id) if id else None
            plugin_version = tuple(map(int, version.split('.'))) if version else None
            plugin_docs = dct.pop('__doc__', None)

            # make sure those those are correct
            assert plugin_id, 'Plugin must present an ID'
            assert plugin_version, 'Plugin must present a version'
            assert plugin_docs, 'Plugin must present documentation'
        except AssertionError as err:
            raise InvalidPluginDefinition(str(err))

        # TODO(kornicaemsiter) signature of plugin instantation must accept only axion
        # configuration (single arg)

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
                id=PluginId(plugin_id),
                name=plugin_name,
                version=plugin_version,
                documentation=plugin_docs,
            ),
        )

        return p


class Plugin(metaclass=PluginMeta):
    plugin_info: t.ClassVar[t.Callable[[], 'PluginInfo']]

    def add_api(
            self,
            oas_specification: oas.OASSpecification,
            server_base_path: t.Optional[str] = None,
            *_: None,
            **kwargs: t.Any,
    ) -> None:
        ...


PluginId = t.NewType('PluginId', str)


class PluginInfo(t.NamedTuple):
    id: PluginId
    name: str
    version: t.Tuple[int, ...]
    documentation: str


class InvalidPluginDefinition(ValueError):
    ...
