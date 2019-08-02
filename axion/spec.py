from dataclasses import dataclass
from pathlib import Path
import typing as t

import jinja2
from loguru import logger
import openapi_spec_validator as osv
import yaml

SpecLocation = t.Union[Path, t.Dict[str, t.Any]]
JinjaArguments = t.Dict[str, t.Any]


class UnsupportedSpecVersion(Exception):
    ...


@dataclass(frozen=True)
class SpecInfo:
    title: str
    version: str
    description: t.Optional[str]
    terms_of_service: t.Optional[str]


@dataclass(frozen=True)
class Spec:
    version: str
    info: SpecInfo


def load(
        spec: SpecLocation,
        arguments: t.Optional[JinjaArguments] = None,
) -> Spec:
    if isinstance(spec, dict):
        return _via_dict(spec)
    elif isinstance(spec, Path):
        return _via_path(spec, arguments)
    else:
        raise ValueError('Loading spec is possible either via Path or Dict')


def _via_dict(spec: dict) -> Spec:
    version = spec.get('openapi', '0.0.0')
    if tuple(map(int, version.split('.'))) < (3, 0, 0):
        raise UnsupportedSpecVersion(f'OpenAPI {version} is not supported')

    try:
        osv.validate_v3_spec(spec)
    except osv.exceptions.OpenAPIValidationError:
        logger.exception('Provided spec does not seem to be valid')
        raise
    else:
        return Spec(
            version=version,
            info=SpecInfo(
                title=spec['info']['title'],
                version=spec['info']['version'],
                description=spec['info'].get('description'),
                terms_of_service=spec['info'].get('termsOfService'),
            ),
        )


def _via_path(
        spec: Path,
        arguments: t.Optional[JinjaArguments] = None,
) -> Spec:
    with spec.open('rb') as handler:
        spec_content = handler.read()
        try:
            openapi_template = spec_content.decode()
        except UnicodeDecodeError:
            openapi_template = spec_content.decode('utf-8', 'replace')

        render_arguments = arguments or {}
        openapi_string = jinja2.Template(openapi_template).render(**render_arguments)
        spec_dict = yaml.safe_load(openapi_string)
    return _via_dict(spec_dict)
