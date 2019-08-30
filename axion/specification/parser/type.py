import functools
import re
import typing as t

from loguru import logger

from axion.specification import exceptions
from axion.specification import model
from axion.specification.parser import ref


def resolve(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASType[t.Any]:
    if '$ref' in work_item:
        logger.opt(
            lazy=True,
            record=True,
        ).debug(
            'Following reference {ref}',
            ref=lambda: work_item['$ref'],
        )
        return resolve(
            components,
            ref.resolve(components, work_item['$ref']),
        )
    elif 'type' in work_item:
        oas_type = work_item['type']
        logger.opt(lazy=True).debug(
            'Resolving schema of type={type}',
            type=lambda: oas_type,
        )
        resolvers = {
            'number': functools.partial(_build_oas_number, float),
            'integer': functools.partial(_build_oas_number, int),
            'boolean': _build_oas_boolean,
            'string': _build_oas_string,
            'array': functools.partial(_build_oas_array, components),
            'object': functools.partial(_build_oas_object, components),
        }  # type:  t.Dict[str, t.Callable[[t.Dict[str, t.Any]], model.OASType[t.Any]]]
        return resolvers[oas_type](work_item)
    elif set(work_item.keys()).intersection(['anyOf', 'allOf', 'oneOf']):
        return _build_oas_mix(components, work_item)
    else:
        return _build_oas_any(work_item)


def _build_oas_any(work_item: t.Dict[str, t.Any]) -> model.OASAnyType:
    return model.OASAnyType(
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        default=work_item.get('default'),
        example=work_item.get('example'),
    )


def _build_oas_mix(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> t.Union[model.OASAnyType, model.OASMixedType[t.Any]]:
    def _handle_not(
            raw_mixed_schema_or_not: t.Dict[str, t.Any],
    ) -> t.Tuple[bool, model.OASType[t.Any]]:
        negated = raw_mixed_schema_or_not.get('not', None)
        if negated is not None:
            return False, resolve(components, negated)
        else:
            return True, resolve(components, raw_mixed_schema_or_not)

    def _resolve_common(
            mix_kind: model.OASMixedType.Kind,
            mix_definition: t.List[t.Dict[str, t.Any]],
    ) -> model.OASMixedType[t.Any]:
        return model.OASMixedType(
            nullable=bool(work_item.get('nullable', False)),
            read_only=bool(work_item.get('readOnly', False)),
            write_only=bool(work_item.get('writeOnly', False)),
            deprecated=bool(work_item.get('deprecated', False)),
            default=work_item.get('default'),
            example=work_item.get('example'),
            kind=mix_kind,
            sub_schemas=[
                _handle_not(mixed_type_schema) for mixed_type_schema in mix_definition
            ],
        )

    def _resolve_any_of(
            mix_kind: model.OASMixedType.Kind,
            mix_definition: t.List[t.Dict[str, t.Any]],
    ) -> t.Union[model.OASAnyType, model.OASMixedType[t.Any]]:
        oas_types = set(
            map(
                lambda e: e['type'] if (len(e) <= 2 and 'type' in e) else None,
                mix_definition,
            ),
        )
        if oas_types == {
                'string',
                'number',
                'integer',
                'boolean',
                'array',
                'object',
        }:
            return _build_oas_any(work_item)
        else:
            return _resolve_common(mix_kind, mix_definition)

    def _resolve_mix_key() -> str:
        if 'anyOf' in work_item:
            return 'anyOf'
        elif 'oneOf' in work_item:
            return 'oneOf'
        return 'allOf'

    resolvers = {
        'anyOf': _resolve_any_of,
        'oneOf': _resolve_common,
        'allOf': _resolve_common,
    }

    mix_key = _resolve_mix_key()
    mix_kind = model.OASMixedType.Kind(mix_key)
    return resolvers[mix_key](mix_kind, work_item[mix_key])


def _build_oas_array(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASArrayType:
    items_schema = work_item['items']
    items_oas_type = resolve(
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
                value = resolve(
                    components,
                    raw_additional_properties,
                )
        else:
            value = raw_additional_properties

        return value

    properties = {
        name: resolve(
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
