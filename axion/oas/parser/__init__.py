import typing as t

from loguru import logger
import openapi_spec_validator as osv
import yarl

from axion.oas import model
from axion.oas.parser import ref as parse_ref
from axion.oas.parser import type as parse_type

P = t.Union[model.OASHeaderParameter,
            model.OASPathParameter,
            model.OASCookieParameter,
            model.OASQueryParameter,
            ]


def parse_spec(spec: t.Dict[str, t.Any]) -> model.OASSpecification:
    try:
        osv.validate_v3_spec(spec)
    except osv.exceptions.OpenAPIValidationError:
        logger.exception('Provided specification does not seem to be valid')
        raise
    else:
        return model.OASSpecification(
            version=spec['openapi'],
            servers=[
                model.OASServer(
                    url=s['url'],
                    variables={
                        k: v['default']
                        for k, v in s.get('variables', {}).items()
                    },
                ) for s in spec['servers']
            ],
            operations=_resolve_operations(
                paths=spec.get('paths', {}),
                components=spec.get('components', {}),
            ),
        )


# extractors for specific parts
def _resolve_operations(
    paths: t.Dict['str', t.Dict[str, t.Any]],
    components: t.Dict['str', t.Dict[str, t.Any]],
) -> model.OASOperations:
    logger.opt(lazy=True).trace('Checking out {count} of paths', count=lambda: len(paths))
    operations = set()
    for op_path, op_path_definition in paths.items():
        for ignore_path_key in ('summary', 'description', 'servers'):
            op_path_definition.pop(ignore_path_key, None)

        global_parameters = _resolve_parameters(
            components,
            op_path_definition.pop('parameters', []),
        )

        logger.opt(
            lazy=True,
            record=True,
        ).trace(
            'Resolved {count} global parameters',
            count=lambda: len(global_parameters),
        )

        for op_http_method in op_path_definition:
            definition = op_path_definition[op_http_method]
            operation_parameters = _resolve_parameters(
                components,
                definition.pop('parameters', []),
            ).union(global_parameters)

            operation = model.OASOperation(
                id=model.OASOperationId(definition['operationId']),
                path=yarl.URL(op_path),
                http_method=model.HTTPMethod(op_http_method),
                deprecated=bool(definition.get('deprecated', False)),
                responses=_resolve_responses(
                    responses_dict=definition['responses'],
                    components=components,
                ),
                request_body=_resolve_request_body(
                    request_body=definition.get('requestBody'),
                    components=components,
                ),
                parameters=operation_parameters,
            )
            operations.add(operation)

            logger.opt(
                lazy=True,
                record=True,
            ).trace(
                'Resolved operation {operation}',
                operation=lambda: operation,
            )

    return frozenset(operations)


def _resolve_request_body(
    request_body: t.Optional[t.Dict[str, t.Any]],
    components: t.Dict[str, t.Any],
) -> t.Optional[model.OASRequestBody]:
    if not request_body:
        return None

    return model.OASRequestBody(
        required=bool(request_body.get('required', False)),
        content=_resolve_content(
            components=components,
            work_item=request_body,
        ),
    )


def _resolve_responses(
    responses_dict: t.Dict[str, t.Any],
    components: t.Dict[str, t.Any],
) -> model.OASResponses:
    responses = {}

    for rp_code, rp_def in responses_dict.items():
        responses[_response_code(rp_code)] = model.OASResponse(
            headers=frozenset(
                t.cast(
                    model.OASHeaderParameter,
                    _resolve_parameter(
                        components,
                        header_name,
                        header_def,
                        model.OASHeaderParameter,
                    ),
                ) for header_name, header_def in rp_def.get('headers', {}).items()
            ),
            content=_resolve_content(
                components,
                rp_def,
            ),
        )

    return model.OASResponses(responses)


def _resolve_content(
    components: t.Dict[str, t.Dict[str, t.Any]],
    work_item: t.Dict[str, t.Any],
) -> model.OASContent:
    if '$ref' in work_item:
        return _resolve_content(
            components,
            parse_ref.resolve(components, work_item['$ref']),
        )
    elif 'content' in work_item:
        work_item = work_item['content']

        def _build_media_type(
            mime_type: str,
            media_type_def: t.Dict[str, t.Any],
        ) -> model.OASMediaType:
            # raw_example = media_type_def.get('example', None)
            # raw_examples = media_type_def.get('examples', {})
            # raw_encoding = media_type_def.get('encoding', None)

            # if not (raw_example and raw_examples) and schema.example is not None:
            #     raw_examples = [{mime_type: schema.example}]
            # elif raw_examples is None and raw_example is not None:
            #     raw_examples = [{mime_type: raw_example}]

            return model.OASMediaType(
                schema=parse_type.resolve(
                    components,
                    media_type_def['schema'],
                ),
            )

        return {
            model.MimeType(mime_type): _build_media_type(mime_type, work_item[mime_type])
            for mime_type in work_item
        }
    else:
        return {}


def _resolve_parameters(
    components: t.Dict[str, t.Any],
    parameters: t.List[t.Dict[str, t.Any]],
) -> model.OASParameters:
    logger.opt(lazy=True).trace(
        'Resolving {count} of parameters',
        count=lambda: len(parameters),
    )

    resolved_parameters: t.List[model.OASParameter] = []

    for param in parameters:
        if '$ref' in param:
            logger.trace(
                'Parameter defined as $ref, following $ref={ref}',
                ref=param['$ref'],
            )
            param_def = parse_ref.resolve(components, param['$ref'])
        else:
            param_def = param

        param_type_to_cls: t.Mapping[str, t.Type[P]] = {
            'header': model.OASHeaderParameter,
            'path': model.OASPathParameter,
            'query': model.OASQueryParameter,
            'cookie': model.OASCookieParameter,
        }
        param_in = param_type_to_cls[param_def['in']]
        param_name = param_def['name']

        logger.opt(lazy=True).trace(
            'Resolving param={param_name} defined in={param_in}',
            param_name=lambda: param_name,
            param_in=lambda: param_in,
        )

        resolved_parameters.append(
            _resolve_parameter(
                components=components,
                param_name=param_name,
                param_def=param_def,
                param_in=param_in,
            ),
        )

    return frozenset(resolved_parameters)


def _resolve_parameter(
    components: t.Dict[str, t.Dict[str, t.Any]],
    param_name: str,
    param_def: t.Dict[str, t.Any],
    param_in: t.Type[P],
) -> P:
    if '$ref' in param_def:
        return _resolve_parameter(
            components=components,
            param_name=param_name,
            param_def=parse_ref.resolve(components, param_def['$ref']),
            param_in=param_in,
        )
    else:
        # needed to determine proper content carried by the field
        # either schema or content will bet set, otherwise OAS is invalid
        schema = param_def.get('schema', None)
        style = model.OASParameterStyles[param_def.get(
            'style',
            param_in.default_style,
        )]
        content = param_def.get('content', None)

        # post processing fields
        explode = bool(param_def.get('explode', style.name == 'form'))
        required = bool(param_def.get('required', False))
        deprecated = bool(param_def.get('deprecated', False))
        example = param_def.get('example', None)

        # those fields are valid either for cookie or header
        allow_empty_value: t.Optional[bool] = None if 'style' in param_def else bool(
            param_def.get('allowEmptyValue', False),
        )

        final_schema: t.Union[t.Tuple[model.OASType[t.Any],
                                      model.OASParameterStyle,
                                      ], model.OASContent]
        if content is not None:
            final_schema = _resolve_content(components, param_def)
        else:
            if param_in not in style.locations:
                raise ValueError(
                    f'Path param {param_name} has incompatible style {style.name}',
                )
            final_schema = (
                parse_type.resolve(components, schema),
                style,
            )

        if issubclass(param_in, model.OASHeaderParameter):
            if param_name in model.OASReservedHeaders:
                raise ValueError(
                    f'Header parameter name {param_name} is reserved thus invalid',
                )
            return model.OASHeaderParameter(
                name=model.OASParameterName(param_name),
                example=example,
                required=required,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
            )
        elif issubclass(param_in, model.OASPathParameter):
            if not required:
                raise ValueError(
                    f'Path parameter {param_name} must have required set to True',
                )
            return model.OASPathParameter(
                name=model.OASParameterName(param_name),
                example=example,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
            )
        elif issubclass(param_in, model.OASQueryParameter):
            allow_reserved = bool(param_def.get('allowReserved', False))
            return model.OASQueryParameter(
                name=model.OASParameterName(param_name),
                example=example,
                required=required,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
                allow_empty_value=allow_empty_value,
                allow_reserved=allow_reserved,
            )
        elif issubclass(param_in, model.OASCookieParameter):
            return model.OASCookieParameter(
                name=model.OASParameterName(param_name),
                example=example,
                required=required,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
            )
        else:
            raise ValueError(
                f'Cannot build parameter {param_name} '
                f'definition from {param_in}',
            )


def _response_code(val: str) -> model.OASResponseCode:
    try:
        return model.HTTPCode(int(val))
    except ValueError:
        return 'default'
