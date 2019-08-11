from dataclasses import dataclass, field, InitVar
import enum
import typing as t

import typing_extensions as te
import yarl

V = t.TypeVar('V')
HTTPCode = t.NewType('HTTPCode', int)
OASResponseCode = t.Union[HTTPCode, te.Literal['default']]


@enum.unique
class HTTPMethod(str, enum.Enum):
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    TRACE = 'trace'
    PATCH = 'patch'
    HEAD = 'head'
    DELETE = 'delete'


@dataclass(repr=False)
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

    def __repr__(self) -> str:
        return f'{self.type}/{self.subtype}'


OASContent = t.Dict[MimeType, 'OASMediaType']


@dataclass(frozen=True)
class OASResponse:
    headers: t.List['OASHeaderParameter'] = field(default_factory=lambda: [])
    content: 'OASContent' = field(default_factory=lambda: {})

    def is_empty(self) -> bool:
        return not self.content


OASResponses = t.Dict[OASResponseCode, OASResponse]


@dataclass(frozen=True, repr=False)
class OperationKey:
    path: str = field(hash=True)
    http_method: HTTPMethod = field(hash=True)

    def __repr__(self) -> str:
        return f'<{self.http_method.name} {self.path}>'


@dataclass(frozen=True, repr=False)
class OperationParameterKey:
    location: str
    name: str

    def __repr__(self) -> str:
        return f'<{self.name} in {self.location}>'


OperationParameters = t.Dict[OperationParameterKey, 'OASParameter']


@dataclass(frozen=True, repr=False)
class Operation:
    operationId: str
    deprecated: bool
    responses: OASResponses
    parameters: OperationParameters

    def __repr__(self) -> str:
        return f'<{self.operationId} responses_count={len(self.responses)}>'


class Operations(t.Dict[OperationKey, t.List[Operation]]):
    ...


@dataclass(frozen=True)
class Spec:
    operations: Operations
    raw_spec: t.Dict[str, t.Any]


@dataclass(frozen=True)
class OASMediaType:
    schema: 'OASType[t.Any]'
    # TODO fix up examples and encoding later on
    # examples: t.Optional[t.Dict[MimeType, 'OASMediaTypeExample']]
    # encoding: t.Optional[t.Dict[str, 'OASMediaTypeEncoding']]


@dataclass(frozen=True)
class OASMediaTypeExample:
    summary: str
    description: str
    value: t.Any
    externalValue: yarl.URL


@dataclass(frozen=True)
class OASMediaTypeEncoding:
    content_type: MimeType
    style: t.Optional['OASParameterStyle']
    exclude: t.Optional[bool]
    allow_reserved: t.Optional[bool]
    headers: t.Set['OASHeaderParameter'] = field(default_factory=lambda: set())


@dataclass(frozen=True)
class OASType(t.Generic[V]):
    nullable: t.Optional[bool]
    default: t.Optional[V]
    example: t.Optional[V]
    deprecated: t.Optional[bool]  # so we can put a warning
    read_only: t.Optional[bool]  # only in responses
    write_only: t.Optional[bool]  # only in requests


@dataclass(frozen=True)
class OASAnyType(OASType[t.Any]):
    ...


@dataclass(frozen=True)
class OASMixedType(OASType[t.Any]):
    @enum.unique
    class Type(str, enum.Enum):
        UNION = 'allOf'
        EITHER = 'oneOf'
        ANY = 'anyOf'

    type: Type
    in_mix: t.List[t.Tuple[bool, OASType[t.Any]]]


@dataclass(frozen=True)
class OASBooleanType(OASType[bool]):
    ...


@dataclass(frozen=True)
class OASNumberType(OASType[t.Union[float, int]]):
    format: t.Optional[str]
    minimum: t.Optional[t.Union[int, float]]
    maximum: t.Optional[t.Union[int, float]]
    multiple_of: t.Optional[t.Union[int, float]]
    exclusive_minimum: t.Optional[bool]
    exclusive_maximum: t.Optional[bool]


@dataclass(frozen=True)
class OASStringType(OASType[str]):
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    pattern: t.Optional[t.Pattern]
    format: t.Optional[str]


@dataclass(frozen=True)
class OASFileType(OASType[None]):
    example: t.Optional[None] = field(init=False, default=None)
    default: t.Optional[None] = field(init=False, default=None)


@dataclass(frozen=True)
class OASObjectDiscriminator:
    property_name: str
    mapping: t.Optional[t.Dict[str, str]]


@dataclass(frozen=True)
class OASObjectType(OASType[t.Dict[str, t.Any]]):
    properties: t.Optional[t.Dict[str, OASType]]
    required: t.Optional[t.Set]
    min_properties: t.Optional[int]
    max_properties: t.Optional[int]
    additional_properties: t.Optional[t.Union[bool, t.Dict]] = None
    discriminator: t.Optional[OASObjectDiscriminator] = None

    @property
    def is_free_form(self) -> bool:
        if self.additional_properties is not None:
            return isinstance(
                self.additional_properties,
                dict,
            ) or self.additional_properties is True
        else:
            return self.properties is None


@dataclass(frozen=True)
class OASArrayType(OASType[t.Union[t.Set[t.Any], t.List[t.Any]]]):
    items_type: t.Union[OASType, OASAnyType, OASMixedType]
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    unique_items: t.Optional[bool]


OASPrimitiveType = t.Union[OASNumberType, OASStringType, OASBooleanType]


@dataclass(frozen=True)
class OASParameter:
    name: str
    schema: t.Union[t.Tuple[OASType, 'OASParameterStyle'], OASContent]
    example: t.Optional[t.Any]
    required: t.Optional[bool]
    explode: t.Optional[bool]
    deprecated: t.Optional[bool]


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
    locations: t.Set[t.Type[OASParameter]]


ParameterLocations = {
    'query': OASQueryParameter,
    'path': OASPathParameter,
    'header': OASHeaderParameter,
    'cookie': OASCookieParameter,
}
ParameterStyleDefaults = {
    OASQueryParameter: 'form',
    OASPathParameter: 'simple',
    OASHeaderParameter: 'simple',
    OASCookieParameter: 'form',
}
# TODO refactor into function
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
        locations={OASQueryParameter, OASCookieParameter},
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
