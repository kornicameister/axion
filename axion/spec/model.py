from dataclasses import dataclass, field, InitVar
import enum
import typing as t

import pydantic as pd
import typing_extensions as te

# use to describe default value
V = t.TypeVar('V')


@enum.unique
class HTTPMethod(str, enum.Enum):
    GET = 'get'
    POST = 'post'
    PUT = 'put'
    TRACE = 'trace'
    PATCH = 'patch'
    HEAD = 'head'
    DELETE = 'delete'


HTTPCode = t.NewType('HTTPCode', int)
OASResponseCode = t.Union[HTTPCode, te.Literal['default']]


@dataclass(repr=False)
class MimeType:
    type: str = field(init=False)
    subtype: str = field(init=False)
    raw_type: InitVar[str]

    def __post_init__(self, raw_type: str) -> None:
        _type, _subtype = raw_type.split('/')
        self.type = _type
        self.subtype = _subtype

    def __repr__(self) -> str:
        return f'{self.type}/{self.subtype}'


@dataclass
class Response:
    model: t.Union['OASType', t.List['OASContent']]


@dataclass
class Responses(t.Dict[OASResponseCode, Response]):
    ...


@dataclass
class Parameter:
    name: str
    type: 'OASType'
    required: t.Optional[bool]
    description: t.Optional[str]
    explode: t.Optional[bool]
    style: str

    def __post_init__(self) -> None:
        if self.type.default is not None and self.required:
            raise ValueError(
                f'{self.name} parameter cannot be both required and have default value'
            )

        if self.explode is None:
            self.explode = self.style == 'form'
        elif not isinstance(self.type, (OASArrayType, OASObjectType)):
            self.explode = None


@dataclass
class PathParameter(Parameter):
    style: str = 'simple'

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.style not in ('matrix', 'label', 'simple'):
            raise ValueError(f'Path param {self.name} has wrong style {self.style}')


@dataclass
class QueryParameter(Parameter):
    allow_reserved: bool = False
    style: str = 'form'

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.style not in ('form', 'spaceDelimited', 'pipeDelimited', 'deepObject'):
            raise ValueError(f'Path param {self.name} has wrong style {self.style}')


@dataclass
class CookieParameter(Parameter):
    style: te.Literal[str] = 'form'

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.style != 'form':
            raise ValueError(f'Path param {self.name} has wrong style {self.style}')


@dataclass
class HeaderParameter(Parameter):
    style: te.Literal[str] = 'simple'

    def __post_init__(self) -> None:
        if self.name.lower() in ('content-type', 'accept', 'authorization'):
            raise ValueError(f'Custom header name {self.name} is not valid')
        elif self.style != 'simple':
            raise ValueError(f'Path param {self.name} has wrong style {self.style}')


@dataclass(frozen=True)
class Parameters:
    path: t.Set[PathParameter] = field(default_factory=set())
    query: t.Set[QueryParameter] = field(default_factory=set())
    header: t.Set[HeaderParameter] = field(default_factory=set())
    cookie: t.Set[CookieParameter] = field(default_factory=set())


@dataclass(frozen=True, repr=False)
class Operation:
    operationId: str
    responses: Responses = field(repr=False)

    def __repr__(self) -> str:
        return f'<{self.operationId} responses_count={len(self.responses)}>'


@dataclass(frozen=True, repr=False)
class OperationKey:
    path: str = field(hash=True)
    http_method: HTTPMethod = field(hash=True)

    def __repr__(self) -> str:
        return f'<{self.http_method.name} {self.path}>'


class Operations(t.Dict[OperationKey, t.Iterable[Operation]]):
    ...


@dataclass(frozen=True)
class Spec:
    operations: Operations
    raw_spec: t.Dict[str, t.Any]


@dataclass(frozen=True)
class OASContent:
    mime_type: MimeType
    oas_type: 'OASType'


@dataclass(frozen=True)
class OASType(t.Generic[V]):
    nullable: t.Optional[bool]
    default: t.Optional[V]
    example: t.Optional[V]
    read_only: t.Optional[bool]  # only in responses
    write_only: t.Optional[bool]  # only in requests


@dataclass(frozen=True)
class OASAnyType(OASType):
    ...


@dataclass(frozen=True)
class OASMixedType(OASType):
    @enum.unique
    class Type(str, enum.Enum):
        UNION = 'allOf'
        EITHER = 'oneOf'
        ANY = 'anyOf'

    type: Type
    in_mix: t.List[t.Tuple[bool, OASType]]


@dataclass(frozen=True)
class OASBooleanType(OASType):
    ...


@dataclass(frozen=True)
class OASNumberType(OASType):
    format: t.Optional[str]
    minimum: t.Optional[t.Union[int, float]]
    maximum: t.Optional[t.Union[int, float]]
    multiple_of: t.Optional[t.Union[int, float]]
    exclusive_minimum: t.Optional[bool]
    exclusive_maximum: t.Optional[bool]


@dataclass(frozen=True)
class OASStringType(OASType):
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    pattern: t.Optional[t.Pattern]
    format: t.Optional[str]


@dataclass(frozen=True)
class OASFileType(OASType):
    example: t.Optional[t.Any] = field(init=False, default=None)
    default: t.Optional[t.Any] = field(init=False, default=None)


@dataclass(frozen=True)
class OASObjectDiscriminator:
    property_name: str
    mapping: t.Optional[t.Dict[str, str]]


@dataclass(frozen=True)
class OASObjectType(OASType):
    properties: t.Optional[t.Dict[str, OASType]]
    required: t.Optional[t.Set]
    min_properties: t.Optional[int]
    max_properties: t.Optional[int]
    additional_properties: t.Optional[t.Union[bool, t.Dict]]
    discriminator: t.Optional[OASObjectDiscriminator]

    @property
    def is_free_form(self) -> bool:
        if self.additional_properties is not None:
            return isinstance(self.additional_properties, dict) or (
                isinstance(self.additional_properties, bool)
                and self.additional_properties is True
            )
        else:
            return self.properties is None


@dataclass(frozen=True)
class OASArrayType(OASType):
    items_type: t.Union[OASType, OASAnyType, OASMixedType]
    min_length: t.Optional[int]
    max_length: t.Optional[int]
    unique_items: t.Optional[bool]
