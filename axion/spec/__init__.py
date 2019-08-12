from pathlib import Path
import re
import typing as t

import jinja2
from loguru import logger
import openapi_spec_validator as osv
import yaml

from axion.spec import exceptions
from axion.spec import model

JinjaArguments = t.Dict[str, t.Any]
SpecLocation = Path


def load(
        spec: SpecLocation,
        arguments: t.Optional[JinjaArguments] = None,
) -> model.Spec:
    if isinstance(spec, Path):
        with spec.open('rb') as handler:
            spec_content = handler.read()
            try:
                openapi_template = spec_content.decode()
            except UnicodeDecodeError:
                openapi_template = spec_content.decode('utf-8', 'replace')

            render_arguments = arguments or {}
            openapi_string = jinja2.Template(openapi_template).render(**render_arguments)
            spec_dict = yaml.safe_load(openapi_string)
        return _parse_spec(spec_dict)
    else:
        raise ValueError(f'Loading spec is not possible via {type(spec)}')


def _parse_spec(spec: t.Dict[str, t.Any]) -> model.Spec:
    try:
        osv.validate_v3_spec(spec)
    except osv.exceptions.OpenAPIValidationError:
        logger.exception('Provided spec does not seem to be valid')
        raise
    else:
        return model.Spec(
            raw_spec=spec,
            operations=_build_operations(
                paths=spec.get('paths', {}),
                components=spec.get('components', {}),
            ),
        )


# extractors for specific parts
def _build_operations(
        paths: t.Dict['str', t.Dict['str', t.Any]],
        components: t.Dict['str', t.Dict['str', t.Any]],
) -> model.Operations:
    logger.opt(lazy=True).trace('Checking out {count} of paths', count=lambda: len(paths))
    operations = model.Operations()
    for op_path, op_path_definition in paths.items():
        if '$ref' in op_path_definition:
            op_path_definition = _follow_ref(components, op_path_definition.pop('$ref'))
        else:
            for ignore_path_key in ('summary', 'description', 'servers'):
                op_path_definition.pop(ignore_path_key, None)

        g_parameters = _resolve_parameters(
            components,
            op_path_definition.pop('parameters', []),
        )
        for op_http_method in op_path_definition:
            http_method = model.HTTPMethod(op_http_method)
            operation_key = model.OperationKey(
                path=op_path,
                http_method=http_method,
            )

            logger.opt(lazy=True).trace(
                'Resolving operation for {key}',
                key=lambda: operation_key,
            )

            definition = op_path_definition[op_http_method]
            if operation_key not in operations:
                operations[operation_key] = []

            l_parameters = _resolve_parameters(
                components,
                definition.pop('parameters', []),
            )
            for param_key, param_def in g_parameters.items():
                if param_key not in l_parameters:
                    # global parameter copied into local parameter
                    l_parameters[param_key] = param_def

            operation = model.Operation(
                operation_id=definition['operationId'],
                deprecated=bool(definition.get('deprecated', False)),
                responses=_build_responses(
                    responses_dict=definition['responses'],
                    components=components,
                ),
                parameters=l_parameters,
            )

            logger.opt(lazy=True).trace(
                '{key} resolved to operation={op}',
                key=lambda: operation_key,
                op=lambda: operation,
            )

            operations[operation_key].append(operation)
    return operations


def _build_responses(
        responses_dict: t.Dict[str, t.Any],
        components: t.Dict[str, t.Any],
) -> model.OASResponses:
    def _resolve_headers(
            raw_headers: t.Dict[str, t.Any],
    ) -> t.List[model.OASHeaderParameter]:
        headers: t.List[model.OASHeaderParameter] = []
        for header_name, header_def in raw_headers.items():
            header = _resolve_parameter(
                components,
                header_name,
                header_def,
                model.OASHeaderParameter,
            )
            headers.append(header)
        return headers

    responses = {}

    for rp_code, rp_def in responses_dict.items():
        responses[_response_code(rp_code)] = model.OASResponse(
            headers=_resolve_headers(rp_def.get('headers', {})),
            content=_resolve_content(
                components,
                rp_def,
            ),
        )

    return responses


def _resolve_content(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASContent:
    if '$ref' in work_item:
        return _resolve_content(
            components,
            _follow_ref(components, work_item['$ref']),
        )
    elif 'content' in work_item:
        work_item = work_item['content']

        def _build_media_type(
                mime_type: str,
                media_type_def: t.Dict[str, t.Any],
        ) -> model.OASMediaType:
            schema = _resolve_schema(components, media_type_def['schema'])

            # raw_example = media_type_def.get('example', None)
            # raw_examples = media_type_def.get('examples', {})
            # raw_encoding = media_type_def.get('encoding', None)

            # if not (raw_example and raw_examples) and schema.example is not None:
            #     raw_examples = [{mime_type: schema.example}]
            # elif raw_examples is None and raw_example is not None:
            #     raw_examples = [{mime_type: raw_example}]

            return model.OASMediaType(schema=schema)

        return {
            model.MimeType(mime_type): _build_media_type(mime_type, work_item[mime_type])
            for mime_type in work_item
        }
    else:
        return {}


P = t.TypeVar(
    'P',
    model.OASCookieParameter,
    model.OASQueryParameter,
    model.OASPathParameter,
    model.OASHeaderParameter,
)


def _resolve_parameters(
        components: t.Dict[str, t.Any],
        parameters: t.List[t.Dict[str, t.Any]],
) -> model.OperationParameters:
    logger.opt(lazy=True).trace(
        'Resolving {count} of parameters',
        count=lambda: len(parameters),
    )
    resolved_parameters: model.OperationParameters = {}
    for param in parameters:
        if '$ref' in param:
            logger.trace(
                'Parameter defined as $ref, following $ref={ref}',
                ref=param['$ref'],
            )
            param_def = _follow_ref(components, param['$ref'])
        else:
            param_def = param

        param_in = param_def['in']
        param_name = param_def['name']

        logger.opt(lazy=True).trace(
            'Resolving param={param_name} defined in={param_in}',
            param_name=lambda: param_name,
            param_in=lambda: param_in,
        )

        param_in_cls = model.ParameterLocations[param_in]
        param_resolved = _resolve_parameter(
            components,
            param_name,
            param_def,
            param_in_cls,
        )
        parameter_key = model.OperationParameterKey(
            location=param_in,
            name=param_name,
        )
        resolved_parameters[parameter_key] = param_resolved

    return resolved_parameters


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
            param_def=_follow_ref(components, param_def['$ref']),
            param_in=param_in,
        )
    else:
        # needed to determine proper content carried by the field
        # either schema or content will bet set, otherwise OAS is invalid
        schema = param_def.get('schema', None)
        style = model.ParameterStyles[param_def.get(
            'style',
            model.ParameterStyleDefaults[param_in],
        )]
        content = param_def.get('content', None)

        # post processing fields
        explode = bool(param_def.get('explode', style.name == 'form'))
        required = bool(param_def.get('required', False))
        deprecated = bool(param_def.get('deprecated', False))
        example = param_def.get('example', None)

        final_schema: t.Union[t.Tuple[model.OASType, model.OASParameterStyle],
                              model.OASContent,
                              ]
        if content is not None:
            final_schema = _resolve_content(components, param_def)
        else:
            if param_in not in style.locations:
                raise ValueError(
                    f'Path param {param_name} has incompatible style {style.name}',
                )
            final_schema = (
                _resolve_schema(components, schema),
                style,
            )

        if issubclass(param_in, model.OASHeaderParameter):
            if param_name.lower() in ('content-type', 'accept', 'authorization'):
                raise ValueError(
                    f'Header parameter name {param_name} is reserved thus invalid',
                )
            return model.OASHeaderParameter(
                name=param_name,
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
                name=param_name,
                example=example,
                required=required,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
            )
        elif issubclass(param_in, model.OASQueryParameter):
            allow_empty_value: t.Optional[bool] = None if 'style' in param_def else bool(
                param_def.get('allowEmptyValue', False),
            )
            allow_reserved: t.Optional[bool] = bool(
                param_def.get('allowReserved', False),
            )

            # TODO figure out why mypy disallows that definition
            return model.OASQueryParameter(  # type: ignore
                name=param_name,
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
                name=param_name,
                example=example,
                required=required,
                explode=explode,
                deprecated=deprecated,
                schema=final_schema,
            )
        else:
            raise ValueError(
                f'Cannot build parameter {param_name} '
                f'definition from {type(param_in)}',
            )


def _resolve_schema(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASType:
    if '$ref' in work_item:
        return _resolve_schema(
            components,
            _follow_ref(components, work_item['$ref']),
        )
    elif 'type' in work_item:
        oas_type = work_item['type']
        if oas_type in ('integer', 'number'):
            return _build_oas_number(work_item)
        elif oas_type == 'boolean':
            return _build_oas_boolean(work_item)
        elif oas_type == 'string':
            return _build_oas_string(work_item)
        elif oas_type == 'array':
            items_schema = work_item['items']
            items_oas_type = _resolve_schema(
                components=components,
                work_item=items_schema,
            )
            return model.OASArrayType(
                items_type=items_oas_type,
                example=work_item.get('example'),
                default=work_item.get('default'),
                min_length=work_item.get('minLength'),
                max_length=work_item.get('maxLength'),
                unique_items=work_item.get('uniqueItems'),
                nullable=work_item.get('nullable'),
                read_only=work_item.get('readOnly'),
                write_only=work_item.get('writeOnly'),
                deprecated=work_item.get('deprecated'),
            )
        elif oas_type == 'object':
            if 'properties' in work_item:
                properties = {
                    name: _resolve_schema(components, property_def)
                    for name, property_def in work_item['properties'].items()
                }  # type: t.Optional[t.Dict[str, model.OASType]]
            else:
                properties = None

            raw_discriminator = work_item.get('discriminator')
            if raw_discriminator is not None:
                discriminator = model.OASObjectDiscriminator(
                    property_name=raw_discriminator['propertyName'],
                    mapping=raw_discriminator.get('mapping'),
                )  # type: t.Optional[model.OASObjectDiscriminator]
            else:
                discriminator = None

            return model.OASObjectType(
                nullable=work_item.get('nullable'),
                default=work_item.get('default'),
                example=work_item.get('example'),
                read_only=work_item.get('readOnly'),
                write_only=work_item.get('writeOnly'),
                required=work_item.get('required'),
                min_properties=work_item.get('minProperties'),
                max_properties=work_item.get('maxProperties'),
                additional_properties=work_item.get('additionalProperties'),
                properties=properties,
                discriminator=discriminator,
                deprecated=work_item.get('deprecated'),
            )
        else:
            raise ValueError(f'Dunno how to resolve type {oas_type}')
    elif set(work_item.keys()).intersection(['anyOf', 'allOf', 'oneOf']):

        def _handle_not(
                raw_mixed_schema_or_not: t.Dict[str, t.Any],
        ) -> t.Tuple[bool, model.OASType]:
            negated = raw_mixed_schema_or_not.get('not', None)
            if negated is not None:
                return False, _resolve_schema(components, negated)
            else:
                return True, _resolve_schema(components, raw_mixed_schema_or_not)

        for mix_key in ('allOf', 'anyOf', 'oneOf'):
            maybe_mix_definition = work_item.get(mix_key, None)
            if maybe_mix_definition is not None:
                mix_type = model.OASMixedType.Type(mix_key)
                in_mix = [
                    _handle_not(mixed_type_schema)
                    for mixed_type_schema in maybe_mix_definition
                ]
                return model.OASMixedType(
                    nullable=work_item.get('nullable'),
                    default=work_item.get('default'),
                    example=work_item.get('example'),
                    read_only=work_item.get('readOnly'),
                    write_only=work_item.get('writeOnly'),
                    type=mix_type,
                    in_mix=in_mix,
                    deprecated=work_item.get('deprecated'),
                )
        else:
            raise ValueError('Failed to determine mix association')  # NOQA
    elif 'type' not in work_item:
        return model.OASAnyType(
            nullable=work_item.get('nullable'),
            default=work_item.get('default'),
            example=work_item.get('example'),
            read_only=work_item.get('readOnly'),
            write_only=work_item.get('writeOnly'),
            deprecated=work_item.get('deprecated'),
        )
    else:
        raise ValueError(f'Cannot deduce how to handle {type(work_item)}: {work_item}')


def _build_oas_string(
        work_item: t.Dict[str, t.Any],
) -> t.Union[model.OASFileType, model.OASStringType]:
    if work_item.get('format', '') == 'binary':
        return model.OASFileType(
            nullable=work_item.get('nullable'),
            read_only=work_item.get('readOnly'),
            write_only=work_item.get('writeOnly'),
            deprecated=work_item.get('deprecated'),
        )
    else:
        # create pattern if possible
        pattern_str = work_item.get('pattern')
        if pattern_str is not None:
            pattern_value = re.compile(pattern_str)  # type: t.Optional[t.Pattern[str]]
        else:
            pattern_value = None

        # ensure that example and default values
        # if set, have the correct type
        default_value: t.Optional[str] = None
        example_value: t.Optional[str] = None
        for key in ('default', 'example'):
            key_value = work_item.get(key)
            if key_value is not None and not isinstance(key_value, str):
                raise exceptions.OASInvalidTypeValue(
                    f'type=string default value has incorrect '
                    f'type={type(key_value)}.'
                    f'Only defualt value that are strings are permitted',
                )
            else:
                if key == 'default':
                    default_value = key_value
                else:
                    example_value = key_value

        # check that minLength < maxLength
        min_length = work_item.get('minLength')
        max_length = work_item.get('maxLength')
        if min_length is not None and max_length is not None:
            if min_length > max_length:
                raise exceptions.OASInvalidConstraints(
                    f'type=string cannot have max_length < min_length. ',
                    f'min_length={min_length} '
                    f'max_length={max_length}.',
                )

        return model.OASStringType(
            default=default_value,
            example=example_value,
            pattern=pattern_value,
            min_length=min_length,
            max_length=max_length,
            nullable=bool(work_item.get('nullable', False)),
            read_only=bool(work_item.get('readOnly', False)),
            write_only=bool(work_item.get('writeOnly', False)),
            deprecated=bool(work_item.get('deprecated', False)),
            format=work_item.get('format'),
        )


def _build_oas_number(work_item: t.Dict[str, t.Any]) -> model.OASNumberType[model.N]:
    return model.OASNumberType(
        nullable=work_item.get('nullable'),
        default=work_item.get('default'),
        example=work_item.get('example'),
        read_only=work_item.get('readOnly'),
        write_only=work_item.get('writeOnly'),
        format=work_item.get('format'),
        minimum=work_item.get('minimum'),
        maximum=work_item.get('maximum'),
        exclusive_minimum=work_item.get('exclusiveMinimum'),
        exclusive_maximum=work_item.get('exclusiveMaximum'),
        multiple_of=work_item.get('multipleOf'),
        deprecated=work_item.get('deprecated'),
    )


def _build_oas_boolean(work_item: t.Dict[str, t.Any]) -> model.OASBooleanType:
    return model.OASBooleanType(
        nullable=work_item.get('nullable'),
        default=work_item.get('default'),
        example=work_item.get('example'),
        read_only=work_item.get('readOnly'),
        write_only=work_item.get('writeOnly'),
        deprecated=work_item.get('deprecated'),
    )


def _follow_ref(
        components: t.Dict[str, t.Any],
        ref: t.Optional[str] = None,
) -> t.Dict[str, t.Any]:
    while ref is not None:
        _, component, name = ref.replace('#/', '').split('/')
        logger.opt(lazy=True).trace(
            'Following ref component="{component}" with name="{name}"',
            component=lambda: component,
            name=lambda: name,
        )
        raw_schema = components[component][name]
        if '$ref' in raw_schema:
            ref = raw_schema['$ref']
        elif isinstance(raw_schema, dict):
            return raw_schema
    raise KeyError(f'No such ref={ref} exist')


def _response_code(val: str) -> model.OASResponseCode:
    try:
        return model.HTTPCode(int(val))
    except ValueError:
        return 'default'
