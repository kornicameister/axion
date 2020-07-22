from pathlib import Path
import typing as t

import pydantic as pd
import typing_extensions as te

__all__ = (
    'Headers',
    'Cookies',
    'HTTPCode',
    'HTTPBody',
    'Response',
)

Headers = t.NewType('Headers', t.Mapping[str, t.Any])
Cookies = t.NewType('Cookies', t.Mapping[str, t.Any])

Body = t.Any
Collection = t.Sequence[Body]
Stream = t.NewType('Stream', t.IO[bytes])
File = t.NewType('File', Path)

HTTPCode = t.NewType('HTTPCode', int)
HTTPBody = t.Optional[t.Union[Stream, Body, Collection, pd.BaseModel]]


class Response(te.TypedDict, total=False):
    body: t.Any
    http_code: int
    headers: t.Mapping[str, t.Any]
    cookies: t.Mapping[str, t.Any]


@te.final
class Request(t.NamedTuple):
    body: HTTPBody
    headers: Headers
    cookies: Cookies
