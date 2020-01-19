import typing as t

from more_itertools import ilen

from axion import conf
from axion import oas


class PluginMeta(type):

    all_known_plugins: t.ClassVar[t.Dict['PluginId', t.Type['Plugin']]] = {}

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

        def _ensure_no_duplicates(p_id: 'PluginId') -> None:
            maybe_plugin = cls.all_known_plugins.get(p_id, None)
            if maybe_plugin is not None and maybe_plugin != p:
                raise InvalidPluginDefinition(
                    f'Plugin with ID={p_id} is already registered as '
                    f'{cls.all_known_plugins[p_id].__qualname__}',
                )

        def _is_axion_configuration(v: t.Any) -> bool:
            return issubclass(v, conf.Configuration)

        def _ensure_correct_init_signature(p_id: 'PluginId') -> None:
            signature = t.get_type_hints(getattr(p, '__init__'))  # noqa
            signature.pop('return')

            has_conf = ilen(filter(_is_axion_configuration, signature.values())) > 0
            has_correct_sig = has_conf and len(signature) == 1

            if not has_correct_sig:
                raise InvalidPluginDefinition(
                    f'Plugin with ID={p_id} has incorrect __init__ signature. '
                    f'It should accept single argument '
                    f'of {repr(conf.Configuration)} type.',
                )

        plugin_name = str(name)

        try:
            # user-set attributes that axion needs
            plugin_id = PluginId(id) if id else None
            plugin_version = tuple(map(int, version.split('.'))) if version else None
            plugin_docs = dct.pop('__doc__', None)

            # make sure those those are correct
            assert plugin_id, 'Plugin must present an ID'
            assert plugin_version, 'Plugin must present a version'
            assert plugin_docs, 'Plugin must present documentation'

            # check if no duplicate
            _ensure_no_duplicates(plugin_id)

            # check if init is correct
            _ensure_correct_init_signature(plugin_id)
        except AssertionError as err:
            raise InvalidPluginDefinition(str(err))

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
                id=plugin_id,
                name=plugin_name,
                version=plugin_version,
                documentation=plugin_docs,
            ),
        )

        cls.all_known_plugins[plugin_id] = p

        return p


class Plugin(metaclass=PluginMeta):
    plugin_info: t.ClassVar[t.Callable[[], 'PluginInfo']]

    def __init__(self, configuration: conf.Configuration) -> None:
        self.configuration = configuration

    def add_api(
            self,
            spec: oas.OASSpecification,
            *_: None,
            base_path: t.Optional[str] = None,
            **kwargs: t.Any,
    ) -> None:
        ...  # pragma: no cover


PluginId = t.NewType('PluginId', str)


class PluginInfo(t.NamedTuple):
    id: PluginId
    name: str
    version: t.Tuple[int, ...]
    documentation: str


class InvalidPluginDefinition(ValueError):
    ...
