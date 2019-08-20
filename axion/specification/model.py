import abc
import enum
import typing as t

import typing_extensions as te
import yarl

HTTPCode = t.NewType('HTTPCode', int)

PTC = t.Type[t.Union[str,
                     float,
                     int,
                     bool,
                     t.Dict[t.Any, t.Any],
                     t.List[t.Any],
                     t.AbstractSet[t.Any],
                     object,
                     ],
             ]


class PythonTypeCompatible(abc.ABC):
    @property
    @abc.abstractmethod
    def python_type(self) -> PTC:
        # typing on its own does not have a type
        # try reveal_type(t.Optional[str]) for instance
        # and see that it says 'Any'
        ...  # pragma: no cover


@enum.unique
class HTTPMethod(str, enum.Enum):
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    TRACE = 'trace'
    PATCH = 'patch'
    HEAD = 'head'
    DELETE = 'delete'


@te.final
class MimeType:
    __slots__ = (
        'type',
        'subtype',
    )

    def __init__(self, raw_type: str) -> None:
        _type, _subtype = raw_type.split('/')
        self.type = _type.lower()
        self.subtype = _subtype.lower()

    def is_json(self) -> bool:
        return 'json' in self.subtype and self.type == 'application'

    def __hash__(self) -> int:
        return hash(self.type + '/' + self.subtype)


OASContent = t.Dict[MimeType, 'OASMediaType']
OASResponseCode = t.Union[HTTPCode, te.Literal['default']]
OASResponses = t.Dict[OASResponseCode, 'OASResponse']
OASOperationId = t.NewType('OASOperationId', str)
OASOperations = t.FrozenSet['OASOperation']


@te.final
class OASResponse:
    __slots__ = (
        'headers',
        'content',
    )

    def __init__(
            self,
            headers: t.List['OASHeaderParameter'],
            content: 'OASContent',
    ) -> None:
        self.headers = headers
        self.content = content


@te.final
class OperationParameters(t.List['OASParameter']):
    def names(self) -> t.FrozenSet[str]:
        return frozenset(map(lambda p: p.name, self))


@te.final
class OASOperation:
    __slots__ = (
        'id',
        'path',
        'http_method',
        'deprecated',
        'responses',
        'parameters',
    )

    def __init__(
            self,
            id: str,
            path: yarl.URL,
            http_method: HTTPMethod,
            deprecated: bool,
            responses: OASResponses,
            parameters: OperationParameters,
    ) -> None:
        self.id = id
        self.path = path
        self.http_method = http_method
        self.deprecated = deprecated
        self.responses = responses
        self.parameters = parameters

    def __hash__(self) -> int:
        return hash(self.id) * hash(self.http_method) * hash(self.path)

    def __repr__(self) -> str:
        return (
            f'[{self.id}] {self.http_method.name} -> {self.path.human_repr()}'
        )  # pragma: no cover


@te.final
class OASServer:
    __slots__ = (
        'url',
        'variables',
    )

    def __init__(
            self,
            url: str,
            variables: t.Dict[str, str],
    ) -> None:
        self.url = url
        self.variables = variables


@te.final
class OASSpecification:
    __slots__ = (
        'version',
        'servers',
        'operations',
    )

    def __init__(
            self,
            version: str,
            servers: t.List[OASServer],
            operations: OASOperations,
    ) -> None:
        self.version = version
        self.servers = servers
        self.operations = operations


@te.final
class OASMediaType:
    __slots__ = ('schema')

    def __init__(
            self,
            schema: 'OASType[t.Any]',
    ) -> None:
        self.schema = schema

    # TODO fix up examples and encoding later on
    # examples: t.Optional[t.Dict[MimeType, 'OASMediaTypeExample']]
    # encoding: t.Optional[t.Dict[str, 'OASMediaTypeEncoding']]


V = t.TypeVar('V')


class OASType(t.Generic[V], PythonTypeCompatible):
    __slots__ = (
        'default',
        'example',
        'nullable',
        'deprecated',
        'read_only',
        'write_only',
    )

    def __init__(
            self,
            default: t.Optional[V],
            example: t.Optional[V],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],  # so we can put a warning
            read_only: t.Optional[bool],  # only in responses
            write_only: t.Optional[bool],  # only in requests
    ) -> None:
        self.default = default
        self.example = example
        self.nullable = nullable
        self.deprecated = deprecated
        self.read_only = read_only
        self.write_only = write_only


@te.final
class OASAnyType(OASType[t.Any]):
    @property
    def python_type(self) -> t.Type[object]:
        return object


@te.final
class OASMixedType(OASType[V]):
    __slots__ = (
        'kind',
        'sub_schemas',
    )

    @enum.unique
    class Kind(str, enum.Enum):
        UNION = 'allOf'
        EITHER = 'oneOf'
        ANY = 'anyOf'

    def __init__(
            self,
            default: t.Optional[V],
            example: t.Optional[V],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
            kind: Kind,
            sub_schemas: t.List[t.Tuple[bool, OASType[t.Any]]],
    ) -> None:
        super().__init__(
            default=default,
            example=example,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )
        self.kind = kind
        self.sub_schemas = sub_schemas

    @property
    def python_type(self) -> t.Type[t.Dict[t.Any, t.Any]]:
        return dict  # pragma: no cover


@te.final
class OASBooleanType(OASType[bool]):
    @property
    def python_type(self) -> t.Type[bool]:
        return bool


N = t.Union[float, int]


@te.final
class OASNumberType(OASType[N]):
    __slots__ = (
        'format',
        'minimum',
        'maximum',
        'multiple_of',
        'exclusive_maximum',
        'exclusive_minimum',
        'number_cls',
    )

    def __init__(
            self,
            default: t.Optional[N],
            example: t.Optional[N],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
            number_cls: t.Type[N],
            format: t.Optional[str],
            minimum: t.Optional[N],
            maximum: t.Optional[N],
            multiple_of: t.Optional[N],
            exclusive_minimum: t.Optional[bool],
            exclusive_maximum: t.Optional[bool],
    ) -> None:
        super().__init__(
            default=default,
            example=example,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )
        self.number_cls = number_cls
        self.format = format
        self.minumum = minimum
        self.maximum = maximum
        self.multiple_of = multiple_of
        self.exclusive_maximum = exclusive_maximum
        self.exclusive_minimum = exclusive_minimum

    @property
    def python_type(self) -> t.Type[N]:
        return self.number_cls


@te.final
class OASStringType(OASType[str]):
    __slots__ = (
        'min_length',
        'max_length',
        'pattern',
        'format',
    )

    def __init__(
            self,
            default: t.Optional[str],
            example: t.Optional[str],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
            min_length: t.Optional[int],
            max_length: t.Optional[int],
            pattern: t.Optional[t.Pattern[str]],
            format: t.Optional[str],
    ) -> None:
        super().__init__(
            default=default,
            example=example,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.format = format

    @property
    def python_type(self) -> t.Type[str]:
        return str


@te.final
class OASFileType(OASType[None]):
    def __init__(
            self,
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
    ) -> None:
        super().__init__(
            default=None,
            example=None,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )

    @property
    def python_type(self) -> t.Type[str]:
        return str


@te.final
class OASObjectDiscriminator:
    __slots__ = (
        'property_name',
        'mapping',
    )

    def __init__(
            self,
            property_name: str,
            mapping: t.Optional[t.Dict[str, str]] = None,
    ) -> None:
        self.property_name = property_name
        self.mapping = mapping


@te.final
class OASObjectType(OASType[t.Dict[str, t.Any]]):
    __slots__ = (
        'min_properties',
        'max_properties',
        'properties',
        'required',
        'additional_properties',
        'discriminator',
    )

    def __init__(
            self,
            default: t.Optional[t.Dict[str, t.Any]],
            example: t.Optional[t.Dict[str, t.Any]],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
            min_properties: t.Optional[int] = None,
            max_properties: t.Optional[int] = None,
            properties: t.Optional[t.Dict[str, OASType[t.Any]]] = None,
            required: t.Optional[t.Set[str]] = None,
            additional_properties: t.Union[bool, OASType[t.Any]] = True,
            discriminator: t.Optional[OASObjectDiscriminator] = None,
    ) -> None:
        super().__init__(
            default=default,
            example=example,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )
        self.min_properties = min_properties
        self.max_properties = max_properties
        self.properties = properties or {}
        self.required = required or set()
        self.additional_properties = additional_properties
        self.discriminator = discriminator

    @property
    def python_type(self) -> t.Type[t.Dict[t.Any, t.Any]]:
        return dict

    @property
    def is_free_form(self) -> bool:
        if self.properties:
            return False
        else:
            return self.additional_properties is True


class OASArrayType(OASType[t.Iterable[t.Any]]):
    __slots__ = (
        'items_type',
        'min_length',
        'max_length',
        'unique_items',
    )

    def __init__(
            self,
            default: t.Optional[t.Iterable[t.Any]],
            example: t.Optional[t.Iterable[t.Any]],
            nullable: t.Optional[bool],
            deprecated: t.Optional[bool],
            read_only: t.Optional[bool],
            write_only: t.Optional[bool],
            items_type: OASType[t.Any],
            min_length: t.Optional[int],
            max_length: t.Optional[int],
            unique_items: t.Optional[bool],
    ) -> None:
        super().__init__(
            default=default,
            example=example,
            nullable=nullable,
            deprecated=deprecated,
            read_only=read_only,
            write_only=write_only,
        )
        self.items_type = items_type
        self.min_length = min_length
        self.max_lenght = max_length
        self.unique_items = unique_items

    @property
    def python_type(self) -> t.Type[t.Union[t.AbstractSet[t.Any], t.List[t.Any]]]:
        return set if self.unique_items else list


class OASParameter(PythonTypeCompatible, abc.ABC):
    __slots__ = (
        'name',
        'schema',
        'example',
        'required',
        'explode',
        'deprecated',
    )
    default_style: t.ClassVar[str] = ''
    available_styles: t.ClassVar[t.AbstractSet[str]] = set()

    def __init__(
            self,
            name: str,
            schema: t.Union[t.Tuple[OASType[t.Any], 'OASParameterStyle'], OASContent],
            example: t.Optional[t.Any],
            required: t.Optional[bool],
            explode: t.Optional[bool],
            deprecated: t.Optional[bool],
    ) -> None:
        self.name = name
        self.schema = schema
        self.example = example
        self.required = required
        self.explode = explode
        self.deprecated = deprecated

    @property
    def python_type(self) -> t.Type[t.Any]:
        if isinstance(self.schema, tuple):
            oas_type, _ = self.schema
            return oas_type.python_type
        else:
            raise ValueError(
                'No idea yet how to build python type here',
            )  # pragma: no cover


@te.final
class OASPathParameter(OASParameter):
    default_style = 'simple'
    available_styles = {'simple', 'label', 'matrix'}


@te.final
class OASQueryParameter(OASParameter):
    __slots__ = (
        'allow_empty_value',
        'allow_reserved',
    )
    default_style = 'form'
    available_styles = {
        'form',
        'spaceDelimited',
        'pipeDelimited',
        'deepObject',
    }

    def __init__(
            self,
            name: str,
            schema: t.Union[t.Tuple[OASType[t.Any], 'OASParameterStyle'], OASContent],
            example: t.Optional[t.Any],
            required: t.Optional[bool],
            explode: t.Optional[bool],
            deprecated: t.Optional[bool],
            allow_empty_value: t.Optional[bool],
            allow_reserved: t.Optional[bool],
    ) -> None:
        super().__init__(name, schema, example, required, explode, deprecated)
        self.allow_empty_value = allow_empty_value
        self.allow_reserved = allow_reserved


@te.final
class OASCookieParameter(OASParameter):
    __slots__ = ('allow_empty_value')
    default_style = 'form'
    available_styles = {'form'}

    def __init__(
            self,
            name: str,
            schema: t.Union[t.Tuple[OASType[t.Any], 'OASParameterStyle'], OASContent],
            example: t.Optional[t.Any],
            required: t.Optional[bool],
            explode: t.Optional[bool],
            deprecated: t.Optional[bool],
            allow_empty_value: t.Optional[bool],
    ) -> None:
        super().__init__(name, schema, example, required, explode, deprecated)
        self.allow_empty_value = allow_empty_value


@te.final
class OASHeaderParameter(OASParameter):
    default_style = 'simple'
    available_styles = {'form'}


@te.final
class OASParameterStyle:
    __slots__ = (
        'name',
        'type',
        'locations',
    )

    def __init__(
            self,
            name: str,
            type: t.Set[t.Type[OASType[t.Any]]],
            locations: t.Set[t.Type[OASParameter]],
    ) -> None:
        self.name = name
        self.type = type
        self.locations = locations


ParameterStyles: t.Dict[str, OASParameterStyle] = {
    'form': OASParameterStyle(
        name='form',
        type={
            OASNumberType,
            OASStringType,
            OASBooleanType,
            OASObjectType,
            OASArrayType,
        },
        locations={
            OASQueryParameter,
            OASCookieParameter,
        },
    ),
    'label': OASParameterStyle(
        name='label',
        type={
            OASNumberType,
            OASStringType,
            OASBooleanType,
            OASObjectType,
            OASArrayType,
        },
        locations={OASPathParameter},
    ),
    'matrix': OASParameterStyle(
        name='matrix',
        type={
            OASNumberType,
            OASStringType,
            OASBooleanType,
            OASObjectType,
            OASArrayType,
        },
        locations={OASPathParameter},
    ),
    'simple': OASParameterStyle(
        name='simple',
        type={OASArrayType},
        locations={OASPathParameter, OASHeaderParameter},
    ),
    'spaceDelimited': OASParameterStyle(
        name='spaceDelimited',
        type={OASArrayType},
        locations={OASQueryParameter},
    ),
    'pipeDelimited': OASParameterStyle(
        name='pipeDelimited',
        type={OASArrayType},
        locations={OASQueryParameter},
    ),
    'deepObject': OASParameterStyle(
        name='deepObject',
        type={OASObjectType},
        locations={OASQueryParameter},
    ),
}
