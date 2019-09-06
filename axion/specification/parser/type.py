import functools
import re
import typing as t

from loguru import logger

from axion.specification import exceptions
from axion.specification import model
from axion.specification.parser import all_of
from axion.specification.parser import ref

__all__ = ('resolve', )


def resolve(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASType[t.Any]:
    if '$ref' in work_item:
        logger.opt(
            lazy=True,
            record=True,
        ).trace(
            'Following reference {ref}',
            ref=lambda: work_item['$ref'],
        )
        return resolve(
            components,
            ref.resolve(components, work_item['$ref']),
        )
    elif 'type' in work_item:
        oas_type = work_item['type']
        logger.opt(
            lazy=True,
            record=True,
        ).trace(
            'Resolving schema of type={type}',
            type=lambda: oas_type,
        )
        resolvers = {
            'number': functools.partial(_resolve_oas_number, float),
            'integer': functools.partial(_resolve_oas_number, int),
            'boolean': _resolve_oas_boolean,
            'string': _resolve_oas_string,
            'array': functools.partial(_resolve_oas_array, components),
            'object': functools.partial(_resolve_oas_object, components),
        }  # type:  t.Dict[str, t.Callable[[t.Dict[str, t.Any]], model.OASType[t.Any]]]
        return resolvers[oas_type](work_item)
    elif 'anyOf' in work_item:
        return _resolve_any_of(
            components=components,
            work_item=work_item,
        )
    elif 'oneOf' in work_item:
        return _resolve_one_of(
            components=components,
            work_item=work_item,
        )
    elif 'allOf' in work_item:
        return _resolve_all_of(
            components=components,
            work_item=work_item,
        )
    else:
        return _resolve_oas_any(work_item)


def _resolve_oas_any(work_item: t.Dict[str, t.Any]) -> model.OASAnyType:
    return model.OASAnyType(
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        default=work_item.get('default'),
        example=work_item.get('example'),
    )


def _resolve_one_of(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASOneOfType:
    mix_definition: t.List[t.Dict[str, t.Any]] = work_item.get('oneOf', [])

    schemas = [
        _handle_any_one_all_of_not(
            components=components,
            work_item=mixed_type_schema,
        ) for mixed_type_schema in mix_definition
    ]
    discriminator = _resolve_discriminator(work_item)
    if discriminator is None:
        discriminator = next(
            filter(
                lambda sd: sd is not None,
                map(
                    lambda s: s[1].discriminator if isinstance(
                        s[1],
                        (
                            model.OASObjectType,
                            model.OASOneOfType,
                            model.OASAnyOfType,
                        ),
                    ) else None,
                    schemas,
                ),
            ),
            None,
        )

    return model.OASOneOfType(
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        default=work_item.get('default'),
        example=work_item.get('example'),
        schemas=schemas,
        discriminator=discriminator,
    )


def _resolve_all_of(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASType[t.Any]:
    # check what allOf stuff we build
    # - check if there is a conflict in definitions
    # - https://json-schema.org/understanding-json-schema/reference/combining.html#allof
    # pick the type and go with normal resolution along with
    # merging the resolved models
    mix_definition: t.List[t.Dict[str, t.Any]] = work_item.get('allOf', [])

    resolved_mix_def = list(
        map(
            lambda mx: ref.resolve(components, mx['$ref']) if '$ref' in mx else mx,
            mix_definition,
        ),
    )
    schema_types: t.Set[str] = set(
        filter(
            lambda mx: mx is not None,
            map(
                lambda mx: mx.get('type', None),  # type: ignore
                resolved_mix_def,
            ),
        ),
    )

    if len(schema_types) == 0:
        oas_type = 'any'
    elif len(schema_types) > 1:
        raise exceptions.OASConflict(
            f'allOf cannot combine more then one OAS type. '
            f'Detected those types [{", ".join(iter(map(repr, schema_types)))}]',
        )
    else:
        oas_type = list(schema_types)[0]

    logger.opt(
        record=True,
        lazy=True,
    ).trace(
        'allOf resolves into type: {oas_type}',
        oas_type=lambda: oas_type,
    )

    all_of_merged = all_of.merge(oas_type, {}, work_item)
    for sub_schema in resolved_mix_def:
        all_of_merged = all_of.merge(oas_type, all_of_merged, sub_schema)
    return resolve(components=components, work_item=all_of_merged)


def _resolve_any_of(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> t.Union[model.OASAnyType, model.OASAnyOfType]:
    mix_definition: t.List[t.Dict[str, t.Any]] = work_item.get('anyOf', [])

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
        return _resolve_oas_any(work_item)
    else:
        schemas = [
            _handle_any_one_all_of_not(
                components=components,
                work_item=mixed_type_schema,
            ) for mixed_type_schema in mix_definition
        ]
        discriminator = _resolve_discriminator(work_item)
        if discriminator is None:
            discriminator = next(
                filter(
                    lambda sd: sd is not None,
                    map(
                        lambda s: s[1].discriminator if isinstance(
                            s[1],
                            (
                                model.OASObjectType,
                                model.OASOneOfType,
                                model.OASAnyOfType,
                            ),
                        ) else None,
                        schemas,
                    ),
                ),
                None,
            )

        return model.OASAnyOfType(
            nullable=bool(work_item.get('nullable', False)),
            read_only=bool(work_item.get('readOnly', False)),
            write_only=bool(work_item.get('writeOnly', False)),
            deprecated=bool(work_item.get('deprecated', False)),
            default=work_item.get('default'),
            example=work_item.get('example'),
            schemas=schemas,
            discriminator=discriminator,
        )


def _handle_any_one_all_of_not(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> t.Tuple[bool, model.OASType[t.Any]]:
    negated = work_item.get('not', None)
    if negated is not None:
        return False, resolve(components, negated)
    else:
        return True, resolve(components, work_item)


def _resolve_oas_array(
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


def _resolve_oas_object(
        components: t.Dict[str, t.Dict[str, t.Any]],
        work_item: t.Dict[str, t.Any],
) -> model.OASObjectType:
    def _resolve_additional_properties() -> t.Union[bool, model.OASType[t.Any]]:
        raw_additional_properties = work_item.get(
            'additionalProperties',
            True,
        )  # type: t.Optional[t.Union[bool, t.Dict[str, t.Any]]]
        if raw_additional_properties is None:
            value = True  # type: t.Union[bool, model.OASType[t.Any]]
        elif not isinstance(raw_additional_properties, bool):
            # it may either be an empty dict or schema
            if len(raw_additional_properties) == 0:
                value = True
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

    discriminator = _resolve_discriminator(work_item=work_item)
    if discriminator is not None:
        property_name = discriminator.property_name
        if property_name not in properties and not additional_properties:
            raise ValueError(
                f'Discriminator {property_name} not found in '
                f'object properties [{", ".join(properties.keys())}]',
            )

    return model.OASObjectType(
        required=set(work_item.get('required', [])),
        additional_properties=additional_properties,
        properties=properties,
        discriminator=discriminator,
        nullable=work_item.get('nullable'),
        read_only=work_item.get('readOnly'),
        write_only=work_item.get('writeOnly'),
        deprecated=work_item.get('deprecated'),
        default=work_item.get('default'),
        example=work_item.get('example'),
        min_properties=work_item.get('minProperties'),
        max_properties=work_item.get('maxProperties'),
    )


def _resolve_discriminator(
        work_item: t.Dict[str, t.Any],
) -> t.Optional[model.OASDiscriminator]:
    raw_discriminator = work_item.get('discriminator')
    if raw_discriminator is not None:
        property_name = raw_discriminator['propertyName']
        discriminator = model.OASDiscriminator(
            property_name=property_name,
            mapping=raw_discriminator.get('mapping'),
        )  # type: t.Optional[model.OASDiscriminator]
    else:
        discriminator = None
    return discriminator


def _resolve_oas_string(
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


def _resolve_oas_number(
        number_cls: t.Type[model.N],
        work_item: t.Dict[str, t.Any],
) -> model.OASNumberType:
    detected_types = set()

    default_value: t.Optional[model.N] = None
    example_value: t.Optional[model.N] = None
    minimum_value: t.Optional[model.N] = None
    maximum_value: t.Optional[model.N] = None

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
                minimum_value = number_cls(key_value)
            elif key == 'maximum':
                maximum_value = number_cls(key_value)

    if len(detected_types) == 2:
        raise exceptions.OASInvalidTypeValue(
            f'type=number [{", ".join(keys)}] value must have the same type. '
            f'Currently {len(detected_types)} distinct types were picked up',
        )

    return model.OASNumberType(
        number_cls=number_cls,
        default=default_value,
        example=example_value,
        minimum=minimum_value,
        maximum=maximum_value,
        nullable=bool(work_item.get('nullable', False)),
        read_only=bool(work_item.get('readOnly', False)),
        write_only=bool(work_item.get('writeOnly', False)),
        deprecated=bool(work_item.get('deprecated', False)),
        format=work_item.get('format'),
        exclusive_minimum=work_item.get('exclusiveMinimum'),
        exclusive_maximum=work_item.get('exclusiveMaximum'),
        multiple_of=work_item.get('multipleOf'),
    )


def _resolve_oas_boolean(work_item: t.Dict[str, t.Any]) -> model.OASBooleanType:
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
