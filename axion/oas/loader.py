from pathlib import Path
import typing as t

import jinja2
import yaml

from axion.oas import model
from axion.oas import parser

JinjaArguments = t.Dict[str, t.Any]


def load_spec(
    spec: Path,
    arguments: t.Optional[JinjaArguments] = None,
) -> model.OASSpecification:
    if isinstance(spec, Path):
        with spec.open('rb') as handler:
            spec_content = handler.read()
            openapi_template = spec_content.decode('utf-8')

            render_arguments = arguments or {}

            openapi_string = jinja2.Template(openapi_template).render(**render_arguments)
            spec_dict = yaml.safe_load(openapi_string)
        return parser.parse_spec(spec_dict)
    else:
        raise ValueError(f'Loading specification is not possible via {type(spec)}')
