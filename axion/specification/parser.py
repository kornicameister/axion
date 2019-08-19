import functools
import re
import typing as t

from loguru import logger
import openapi_spec_validator as osv
import yarl

from axion.specification import exceptions
from axion.specification import model


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

        logger.opt(lazy=True).debug(
            'Resolved {count} global parameters',
            count=lambda: len(global_parameters),
        )

        for op_http_method in op_path_definition:
            definition = op_path_definition[op_http_method]
            operation_parameters = _resolve_parameters(
                components,
                definition.pop('parameters', []),
            )
            for param_def in global_parameters:
                if param_def.name not in operation_parameters.names():
                    # global parameter copied into local parameter
                    operation_parameters.append(param_def)

            operation = model.OASOperation(
                id=model.OASOperationId(definition['operationId']),
                path=yarl.URL(op_path),
                http_method=model.HTTPMethod(op_http_method),
                deprecated=bool(definition.get('deprecated', False)),
                responses=_resolve_responses(
                    responses_dict=definition['responses'],
                    components=components,
                ),
                parameters=operation_parameters,
            )
            operations.add(operation)

            logger.opt(lazy=True).trace(
                'Resolved operation {operation}',
                operation=lambda: operation,
            )

    return frozenset(operations)


def _resolve_responses(
        responses_dict: t.Dict[str, t.Any],
        components: t.Dict[str, t.Any],
) -> model.OASResponses:
    responses = {}

    for rp_code, rp_def in responses_dict.items():
        responses[_response_code(rp_code)] = model.OASResponse(
            headers=[
                _resolve_parameter(
                    components,
                    header_name,
                    header_def,
                    model.OASHeaderParameter,
                ) for header_name, header_def in rp_def.get('headers', {}).items()
            ],
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


def _resolve_parameters(
        components: t.Dict[str, t.Any],
        parameters: t.List[t.Dict[str, t.Any]],
) -> model.OperationParameters:
    logger.opt(lazy=True).trace(
        'Resolving {count} of parameters',
        count=lambda: len(parameters),
    )

    resolved_parameters = []

    for param in parameters:
        if '$ref' in param:
            logger.trace(
                'Parameter defined as $ref, following $ref={ref}',
                ref=param['$ref'],
            )
            param_def = _follow_ref(components, param['$ref'])
        else:
            param_def = param

        param_in = {
            'header': model.OASHeaderParameter,
            'path': model.OASPathParameter,
            'query': model.OASQueryParameter,
            'cookie': model.OASCookieParameter,
        }[param_def['in']]
        param_name = param_def['name']

        logger.opt(lazy=True).trace(
            'Resolving param={param_name} defined in={param_in}',
            param_name=lambda: param_name,
            param_in=lambda: param_in,
        )

        resolved_parameters.append(
            _resolve_parameter(  # type: ignore
                components=components,
                param_name=param_name,
                param_def=param_def,
                param_in=param_in,
            ),
        )

    return model.OperationParameters(resolved_parameters)


CamelCaseToSnakeCaseRegex = re.compile(r'(?!^)(?<!_)([A-Z])')


def _convert_to_snake_case(s: str) -> str:
    return CamelCaseToSnakeCaseRegex.sub(r'_\1', s).lower()


Param = t.TypeVar(
    'Param',
    model.OASHeaderParameter,
    model.OASPathParameter,
    model.OASCookieParameter,
    model.OASQueryParameter,
)


def _resolve_parameter(
        components: t.Dict[str, t.Dict[str, t.Any]],
        param_name: str,
        param_def: t.Dict[str, t.Any],
        param_in: t.Type[Param],
) -> Param:
    if '$ref' in param_def:
        return _resolve_parameter(
            components=components,
            param_name=param_name,
            param_def=_follow_ref(components, param_def['$ref']),
            param_in=param_in,
        )
    else:
        param_name = _convert_to_snake_case(param_name)
        # needed to determine proper content carried by the field
        # either schema or content will bet set, otherwise OAS is invalid
        schema = param_def.get('schema', None)
        style = model.ParameterStyles[param_def.get(
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
            allow_reserved = bool(param_def.get('allowReserved', False))
            return model.OASQueryParameter(
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
                allow_empty_value=allow_empty_value,
            )
        else:
            raise ValueError(
                f'Cannot build parameter {param_name} '
                f'definition from {param_in}',
            )


def _resolve_schema(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASType[t.Any]:

    resolvers = {
        'number': functools.partial(_build_oas_number, float),
        'integer': functools.partial(_build_oas_number, int),
        'boolean': _build_oas_boolean,
        'string': _build_oas_string,
        'array': functools.partial(_build_oas_array, components),
        'object': functools.partial(_build_oas_object, components),
    }  # type:  t.Dict[str, t.Callable[[t.Dict[str, t.Any]], model.OASType[t.Any]]]

    if '$ref' in work_item:
        return _resolve_schema(
            components,
            _follow_ref(components, work_item['$ref']),
        )
    elif 'type' in work_item:
        oas_type = work_item['type']
        logger.opt(lazy=True).debug(
            'Resolving schema of type={type}',
            type=lambda: oas_type,
        )
        return resolvers[oas_type](work_item)
    elif set(work_item.keys()).intersection(['anyOf', 'allOf', 'oneOf']):

        def _handle_not(
                raw_mixed_schema_or_not: t.Dict[str, t.Any],
        ) -> t.Tuple[bool, model.OASType[t.Any]]:
            negated = raw_mixed_schema_or_not.get('not', None)
            if negated is not None:
                return False, _resolve_schema(components, negated)
            else:
                return True, _resolve_schema(components, raw_mixed_schema_or_not)

        mix_value: model.OASMixedType[t.Any]
        for mix_key in ('allOf', 'anyOf', 'oneOf'):
            maybe_mix_definition = work_item.get(mix_key, None)
            if maybe_mix_definition is not None:
                mix_type = model.OASMixedType.Type(mix_key)
                mix_value = model.OASMixedType(
                    nullable=bool(work_item.get('nullable', False)),
                    read_only=bool(work_item.get('readOnly', False)),
                    write_only=bool(work_item.get('writeOnly', False)),
                    deprecated=bool(work_item.get('deprecated', False)),
                    default=work_item.get('default'),
                    example=work_item.get('example'),
                    mix_type=mix_type,
                    in_mix=[
                        _handle_not(mixed_type_schema)
                        for mixed_type_schema in maybe_mix_definition
                    ],
                )
        return mix_value
    else:
        return model.OASAnyType(
            nullable=bool(work_item.get('nullable', False)),
            read_only=bool(work_item.get('readOnly', False)),
            write_only=bool(work_item.get('writeOnly', False)),
            deprecated=bool(work_item.get('deprecated', False)),
            default=work_item.get('default'),
            example=work_item.get('example'),
        )


def _build_oas_array(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASArrayType:
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


def _build_oas_object(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASObjectType:
    def _resolve_additional_properties() -> t.Union[bool, model.OASType[t.Any]]:
        raw_additional_properties = work_item.get(
            'additionalProperties',
            True,
        )  # type: t.Union[bool, t.Dict[str, t.Any]]

        if not isinstance(raw_additional_properties, bool):
            # it may either be an empty dict or schema
            if len(raw_additional_properties) == 0:
                value = True  # type: t.Union[bool, model.OASType[t.Any]]
            else:
                value = _resolve_schema(
                    components,
                    raw_additional_properties,
                )
        else:
            value = raw_additional_properties

        return value

    properties = {
        name: _resolve_schema(
            components,
            property_def,
        )
        for name, property_def in work_item.get('properties', {}).items()
    }
    additional_properties = _resolve_additional_properties()

    raw_discriminator = work_item.get('discriminator')
    if raw_discriminator is not None:
        property_name = raw_discriminator['propertyName']

        if property_name not in properties and not additional_properties:
            raise ValueError(
                f'Discriminator {property_name} not found in '
                f'object properties [{", ".join(properties.keys())}]',
            )

        discriminator = model.OASObjectDiscriminator(
            property_name=property_name,
            mapping=raw_discriminator.get('mapping'),
        )  # type: t.Optional[model.OASObjectDiscriminator]
    else:
        discriminator = None

    return model.OASObjectType(
        required=set(work_item.get('required', [])),
        additional_properties=additional_properties,
        properties=properties,
        discriminator=discriminator,
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        default=work_item.get('default'),
        example=work_item.get('example'),
        min_properties=work_item.get('minProperties'),
        max_properties=work_item.get('maxProperties'),
    )


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


def _build_oas_number(
        number_cls: t.Type[model.N],
        work_item: t.Dict[str, t.Any],
) -> model.OASNumberType:
    detected_types = set()

    default_value: t.Optional[model.N] = None
    example_value: t.Optional[model.N] = None
    minimum: t.Optional[model.N] = None
    maximum: t.Optional[model.N] = None

    keys = ('default', 'example', 'minimum', 'maximum')
    for key in keys:
        key_value = work_item.get(key)
        if key_value is not None:
            detected_types.add(type(key_value))
            if not isinstance(key_value, (int, float)):
                raise exceptions.OASInvalidTypeValue(
                    f'type=number {key} value has incorrect '
                    f'type={type(key_value)}.'
                    f'Only allowed types for {key} that are either '
                    f'{[int, float]} are permitted',
                )
            elif key == 'default':
                default_value = number_cls(key_value)
            elif key == 'example':
                example_value = number_cls(key_value)
            elif key == 'minimum':
                example_value = number_cls(key_value)
            elif key == 'maximum':
                example_value = number_cls(key_value)

    if len(detected_types) == 2:
        raise exceptions.OASInvalidTypeValue(
            f'type=number {", ".join(keys)} value must have the same type. '
            f'Currently {len(keys)} distinct types were picked up',
        )

    return model.OASNumberType(
        number_cls=number_cls,
        default=default_value,
        example=example_value,
        minimum=minimum,
        maximum=maximum,
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        format=work_item.get('format'),
        exclusive_minimum=work_item.get('exclusiveMinimum'),
        exclusive_maximum=work_item.get('exclusiveMaximum'),
        multiple_of=work_item.get('multipleOf'),
    )


def _build_oas_boolean(work_item: t.Dict[str, t.Any]) -> model.OASBooleanType:
    default_value: t.Optional[bool] = None
    example_value: t.Optional[bool] = None
    keys = ('default', 'example')
    for key in keys:
        key_value = work_item.get(key)
        if key_value is not None:
            if not isinstance(key_value, bool):
                raise exceptions.OASInvalidTypeValue(
                    f'type=boolean {key} value has incorrect '
                    f'type={type(key_value)}. '
                    f'Only allowed types for {key} is {bool}.',
                )
            elif key == 'default':
                default_value = key_value
            elif key == 'example':
                example_value = key_value

    return model.OASBooleanType(
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        default=default_value,
        example=example_value,
    )


def _follow_ref(
        components: t.Dict[str, t.Any],
        ref: t.Optional[str] = None,
) -> t.Dict[str, t.Any]:
    while ref is not None:
        _, component, name = ref.replace('#/', '').split('/')
        logger.opt(lazy=True).debug(
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
