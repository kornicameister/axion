from dataclasses import dataclass, field, InitVar
import enum
import typing as t

import typing_extensions as te
import yarl

HTTPCode = t.NewType('HTTPCode', int)
OASResponseCode = t.Union[HTTPCode, te.Literal['default']]


class PythonTypeCompatible(te.Protocol):
    @property
    def python_type(self) -> t.Any:
        # typing on its own does not have a type
        # try reveal_type(t.Optional[str]) for instance
        # and see that it says 'Any'
        ...


@enum.unique
class HTTPMethod(str, enum.Enum):
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    TRACE = 'trace'
    PATCH = 'patch'
    HEAD = 'head'
    DELETE = 'delete'


@dataclass
class MimeType:
    type: str = field(init=False)
    subtype: str = field(init=False)
    raw_type: InitVar[str]

    def __post_init__(self, raw_type: str) -> None:
        _type, _subtype = raw_type.split('/')
        self.type = _type.lower()
        self.subtype = _subtype.lower()

    def is_json(self) -> bool:
        return 'json' in self.subtype and self.type == 'application'

    def __hash__(self) -> int:
        return hash(self.type + '/' + self.subtype)


OASContent = t.Dict[MimeType, 'OASMediaType']


@dataclass(frozen=True)
class OASResponse:
    headers: t.List['OASParameter'] = field(default_factory=lambda: [])
    content: 'OASContent' = field(default_factory=lambda: {})


OASResponses = t.Dict[OASResponseCode, OASResponse]

OperationId = t.NewType('OperationId', str)


class OperationParameters(t.List['OASParameter']):
    def names(self) -> t.FrozenSet[str]:
        return frozenset(map(lambda p: p.name, self))

    def path_parameters(self) -> t.Iterable['OASPathParameter']:
        return iter(param for param in self if isinstance(param, OASPathParameter))


@dataclass(frozen=True, repr=False)
class OASOperation:
    operation_id: OperationId = field(
        hash=True,
        compare=True,
        metadata={'key': True},
    )
    path: yarl.URL = field(
        hash=True,
        compare=True,
        metadata={'key': True},
    )
    http_method: HTTPMethod = field(
        hash=True,
        compare=True,
        metadata={'key': True},
    )
    deprecated: bool = field(
        hash=False,
        compare=False,
    )
    responses: OASResponses = field(
        hash=False,
        compare=False,
    )
    parameters: OperationParameters = field(
        hash=False,
        compare=False,
    )

    def __repr__(self) -> str:
        return (
            f'[{self.operation_id}] {self.http_method.name} -> {self.path.human_repr()}'
        )  # pragma: no cover


class Operations(t.FrozenSet[OASOperation]):
    ...


@dataclass(frozen=True)
class OASServer:
    url: str
    # does not deal with all possible values
    # just holds the name of the variable
    # and its default value (which is required by OAS)
    variables: t.Dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class OASSpecification:
    version: str
    servers: t.List[OASServer]
    operations: Operations


@dataclass(frozen=True)
class OASMediaType:
    schema: 'OASType'
    # TODO fix up examples and encoding later on
    # examples: t.Optional[t.Dict[MimeType, 'OASMediaTypeExample']]
    # encoding: t.Optional[t.Dict[str, 'OASMediaTypeEncoding']]


@dataclass(frozen=True)
class OASType(PythonTypeCompatible):
    default: t.Optional[t.Any]
    example: t.Optional[t.Any]
    nullable: t.Optional[bool]
    deprecated: t.Optional[bool]  # so we can put a warning
    read_only: t.Optional[bool]  # only in responses
    write_only: t.Optional[bool]  # only in requests


@dataclass(frozen=True)
class OASAnyType(OASType):
    @property
    def python_type(self) -> t.Any:
        return object


@dataclass(frozen=True)
class OASMixedType(OASType):
    @enum.unique
    class Type(str, enum.Enum):
        UNION = 'allOf'
        EITHER = 'oneOf'
        ANY = 'anyOf'

    type: Type
    in_mix: t.List[t.Tuple[bool, OASType]]

    @property
    def python_type(self) -> t.Any:
        return dict


@dataclass(frozen=True)
class OASBooleanType(OASType):
    default: t.Optional[bool]
    example: t.Optional[bool]

    @property
    def python_type(self) -> t.Any:
        return bool


N = t.TypeVar('N', float, int)


@dataclass(frozen=True)
class OASNumberType(OASType, t.Generic[N]):
    number_cls: t.Type[N]
    default: t.Optional[N]
    example: t.Optional[N]
    format: t.Optional[str]
    minimum: t.Optional[N]
    maximum: t.Optional[N]
    multiple_of: t.Optional[t.Union[N]]
    exclusive_minimum: t.Optional[bool]
    exclusive_maximum: t.Optional[bool]

    @property
    def python_type(self) -> t.Any:
        return self.number_cls


@dataclass(frozen=True)
class OASStringType(OASType):
    default: t.Optional[str]
    example: t.Optional[str]
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    pattern: t.Optional[t.Pattern[str]]
    format: t.Optional[str]

    @property
    def python_type(self) -> t.Any:
        return str


@dataclass(frozen=True)
class OASFileType(OASType):
    example: t.Optional[None] = field(init=False, default=None)
    default: t.Optional[None] = field(init=False, default=None)

    @property
    def python_type(self) -> t.Any:
        return str


@dataclass(frozen=True)
class OASObjectDiscriminator:
    property_name: str
    mapping: t.Optional[t.Dict[str, str]]


@dataclass(frozen=True)
class OASObjectType(OASType):
    min_properties: t.Optional[int] = None
    max_properties: t.Optional[int] = None
    properties: t.Dict[str, OASType] = field(default_factory=lambda: {})
    required: t.Set[str] = field(default_factory=lambda: set())
    additional_properties: t.Union[bool, OASType] = True
    discriminator: t.Optional[OASObjectDiscriminator] = None

    @property
    def python_type(self) -> t.Any:
        return dict

    @property
    def is_free_form(self) -> bool:
        if self.properties:
            return False
        else:
            return self.additional_properties is True


@dataclass(frozen=True)
class OASArrayType(OASType):
    items_type: t.Union[OASType, OASMixedType]
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    unique_items: t.Optional[bool]

    @property
    def python_type(self) -> t.Any:
        return list


@dataclass(frozen=True)
class OASParameter(PythonTypeCompatible):
    name: str
    schema: t.Union[t.Tuple[OASType, 'OASParameterStyle'], OASContent]
    example: t.Optional[t.Any]
    required: t.Optional[bool]
    explode: t.Optional[bool]
    deprecated: t.Optional[bool]

    @property
    def python_type(self) -> t.Any:
        if isinstance(self.schema, tuple):

            # TODO most likely that needs to deal with explode stuff
            #      and specialities of style

            oas_type, _ = self.schema
            python_type = oas_type.python_type
            return python_type if self.required else t.Optional[python_type]
        else:
            raise ValueError('No idea yet how to build python type here')


@dataclass(frozen=True)
class OASPathParameter(OASParameter):
    ...


@dataclass(frozen=True)
class OASQueryParameter(OASParameter):
    allow_empty_value: t.Optional[bool]
    allow_reserved: t.Optional[bool]


@dataclass(frozen=True)
class OASCookieParameter(OASParameter):
    ...


@dataclass(frozen=True)
class OASHeaderParameter(OASParameter):
    ...


@dataclass(frozen=True)
class OASParameterStyle:
    name: str
    type: t.Set[t.Type[OASType]]
    locations: t.Set[te.Literal['path', 'cookie', 'query', 'header']]


ParameterStyleDefaults: t.Dict[str, str] = {
    'query': 'form',
    'path': 'simple',
    'header': 'simple',
    'cookie': 'form',
}
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
        locations={'query', 'cookie'},
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
        locations={'path'},
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
        locations={'path'},
    ),
    'simple': OASParameterStyle(
        name='simple',
        type={OASArrayType},
        locations={'path', 'header'},
    ),
    'spaceDelimited': OASParameterStyle(
        name='spaceDelimited',
        type={OASArrayType},
        locations={'query'},
    ),
    'pipeDelimited': OASParameterStyle(
        name='pipeDelimited',
        type={OASArrayType},
        locations={'query'},
    ),
    'deepObject': OASParameterStyle(
        name='deepObject',
        type={OASObjectType},
        locations={'query'},
    ),
}
