from pathlib import Path
import typing as t
import re

import cachetools
import jinja2
from loguru import logger
import openapi_spec_validator as osv
import yaml

from axion.spec import model

JinjaArguments = t.Dict[str, t.Any]
SpecLocation = Path


class UnsupportedSpecVersion(Exception):
    ...


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
        raise ValueError(f'Loading spec is possible either via {type(spec)}')


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
        components: t.Dict['str', t.Dict['str', t.Any]]
) -> model.Operations:
    logger.debug('Checking out {count} of paths', count=len(paths))
    operations = model.Operations()
    for op_path, op_path_definition in paths.items():
        if '$ref' in op_path_definition:
            op_path_definition = _follow_ref(components, op_path_definition.pop('$ref'))
        else:
            for ignore_path_key in ('summary', 'description', 'servers'):
                op_path_definition.pop(ignore_path_key, None)

        global_parameters = op_path_definition.pop('parameters', None)
        for op_http_method in op_path_definition:
            http_method = model.HTTPMethod(op_http_method)
            operation_key = model.OperationKey(
                path=op_path,
                http_method=http_method,
            )

            logger.opt(lazy=True).debug(
                'Resolving operation for {key}',
                key=lambda: operation_key,
            )

            definition = op_path_definition[op_http_method]
            if operation_key not in operations:
                operations[operation_key] = []

            operation = model.Operation(
                operationId=definition['operationId'],
                responses=_build_responses(
                    responses_dict=definition['responses'],
                    components=components,
                ),
            )

            logger.opt(lazy=True).debug(
                '{key} resolved to operation={op}',
                key=lambda: operation_key,
                op=lambda: operation,
            )

            operations[operation_key].append(operation)
    return operations


def _build_responses(
        responses_dict: t.Dict[str, t.Dict[str, t.Any]],
        components: t.Dict[str, t.Dict[str, t.Any]],
) -> model.Responses:
    responses = model.Responses()
    for rp_code, rp_def in responses_dict.items():
        response_code = _response_code(rp_code)
        response_schema = _resolve_schema(
            components=components,
            work_item=rp_def,
        )
        responses[response_code] = model.Response(model=response_schema)
    return responses


class NullOmittingCache(t.Dict[str, t.Union[model.OASType, t.List[model.OASContent]]]):
    def __getitem__(self, k: str):
        if not k:
            raise KeyError('<none>')
        else:
            return super().__getitem__(k)

    def __setitem__(
            self, k: str, v: t.Union[model.OASType, t.List[model.OASContent]]
    ) -> None:
        if k:
            super().__setitem__(k, v)


@cachetools.cached(
    cache=NullOmittingCache(),
    key=lambda *args, **kwargs: kwargs.get('ref')
)
def _resolve_schema(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
        ref: t.Optional[str] = None,
) -> t.Union[model.OASType, t.List[model.OASContent]]:
    if '$ref' in work_item:
        return _resolve_schema(
            components,
            _follow_ref(components, work_item['$ref']),
            ref=work_item['$ref'],
        )
    elif 'content' in work_item:
        work_item = work_item['content']
        return [
            model.OASContent(
                mime_type=model.MimeType(mime_type),
                oas_type=_resolve_schema(components, work_item[mime_type]['schema']),
            ) for mime_type in work_item
        ]
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
            )
        elif oas_type == 'object':
            if 'properties' in work_item:
                properties = {
                    name: _resolve_schema(components, property_def)
                    for name, property_def in work_item['properties'].items()
                }
            else:
                properties = None

            raw_discriminator = work_item.get('discriminator')
            if raw_discriminator is not None:
                discriminator = model.OASObjectDiscriminator(
                    property_name=raw_discriminator['propertyName'],
                    mapping=raw_discriminator.get('mapping'),
                )
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
            )
        else:
            raise ValueError(f'Dunno how to resolve type {oas_type}')
    elif set(work_item.keys()).intersection(['anyOf', 'allOf', 'oneOf']):

        def _handle_not(raw_mixed_schema_or_not: t.Dict[str, t.Any]
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
        )
    else:
        raise ValueError('Something good here')


def _build_oas_string(
        work_item: t.Dict[str, t.Any],
) -> t.Union[model.OASFileType, model.OASStringType]:
    if work_item.get('format', '') == 'binary':
        return model.OASFileType(
            nullable=work_item.get('nullable'),
            read_only=work_item.get('readOnly'),
            write_only=work_item.get('writeOnly'),
        )
    else:
        pattern_str = work_item.get('pattern')
        if pattern_str is not None:
            pattern = re.compile(pattern_str)
        else:
            pattern = None

        return model.OASStringType(
            nullable=work_item.get('nullable'),
            default=work_item.get('default'),
            example=work_item.get('example'),
            read_only=work_item.get('readOnly'),
            write_only=work_item.get('writeOnly'),
            format=work_item.get('format'),
            min_length=work_item.get('minLength'),
            max_length=work_item.get('maxLength'),
            pattern=pattern,
        )


def _build_oas_number(work_item: t.Dict[str, t.Any]) -> model.OASNumberType:
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
    )


def _build_oas_boolean(work_item: t.Dict[str, t.Any]) -> model.OASBooleanType:
    return model.OASBooleanType(
        nullable=work_item.get('nullable'),
        default=work_item.get('default'),
        example=work_item.get('example'),
        read_only=work_item.get('readOnly'),
        write_only=work_item.get('writeOnly'),
    )


@cachetools.cached(cache={}, key=lambda _, ref: ref)
def _follow_ref(
        components: t.Dict[str, t.Dict[str, t.Any]],
        ref: t.Optional[str] = None,
) -> t.Dict[str, t.Dict[str, t.Any]]:
    while ref is not None:
        _, component, name = ref.replace('#/', '').split('/')
        raw_schema = components[component][name]
        if '$ref' in raw_schema:
            ref = raw_schema['$ref']
        else:
            return raw_schema
    return {}


def _response_code(val: str) -> model.OASResponseCode:
    try:
        return model.HTTPCode(int(val))
    except ValueError:
        return 'default'
