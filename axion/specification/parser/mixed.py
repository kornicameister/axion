import copy
import functools
import typing as t

from axion.specification import exceptions
from axion.specification import model

M = t.TypeVar('M', bound=model.OASType[t.Any])
V = t.TypeVar('V')


@functools.singledispatch
def merge(a: M, b: M) -> M:
    raise TypeError(f'merge not implemented for {type(a)}')


@merge.register
def _any(
        a: model.OASAnyType,
        b: model.OASAnyType,
) -> model.OASAnyType:
    return model.OASAnyType(
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        nullable=_get_value('nullable', a.nullable, b.nullable),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
    )


@merge.register
def _boolean(
        a: model.OASBooleanType,
        b: model.OASBooleanType,
) -> model.OASBooleanType:
    return model.OASBooleanType(
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        nullable=_get_value('nullable', a.nullable, b.nullable),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
    )


@merge.register
def _string(
        a: model.OASStringType,
        b: model.OASStringType,
) -> model.OASStringType:
    return model.OASStringType(
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        nullable=_get_value('nullable', a.nullable, b.nullable),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
        min_length=_get_value('minLength', a.min_length, b.min_length),
        max_length=_get_value('maxLength', a.max_length, b.max_length),
        pattern=_get_value('pattern', a.pattern, b.pattern),
        format=_get_value('format', a.format, b.format),
    )


@merge.register
def _number(
        a: model.OASNumberType,
        b: model.OASNumberType,
) -> model.OASNumberType:
    # number_cls is out of comparion here
    # float is for type: number
    # int is for type: integer
    # therefore those are threated as distinct types in axion eyes
    # and cannot be mixed
    return model.OASNumberType(
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        nullable=_get_value('nullable', a.nullable, b.nullable),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
        number_cls=a.number_cls,
        format=_get_value('format', a.format, b.format),
        minimum=_get_value('minimum', a.minimum, b.minimum),
        maximum=_get_value('maximum', a.maximum, b.maximum),
        multiple_of=_get_value('multipleOf', a.multiple_of, b.multiple_of),
        exclusive_minimum=_get_value(
            'exclusiveMinimum',
            a.exclusive_minimum,
            b.exclusive_minimum,
        ),
        exclusive_maximum=_get_value(
            'exclusiveMaximum',
            a.exclusive_maximum,
            b.exclusive_maximum,
        ),
    )


@merge.register
def _array(a: model.OASArrayType, b: model.OASArrayType) -> model.OASArrayType:
    return model.OASArrayType(
        nullable=_get_value('nullable', a.nullable, b.nullable),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        min_length=_get_value('minLength', a.min_length, b.min_length),
        max_length=_get_value('maxLength', a.max_length, b.max_length),
        unique_items=_get_value('uniqueItems', a.unique_items, b.unique_items),
        items_type=t.cast(
            model.OASType[t.Any],
            _get_value(
                'items',
                type(a.items_type),
                type(b.items_type),
            ),
        ),
    )


@merge.register
def _object(a: model.OASObjectType, b: model.OASObjectType) -> model.OASObjectType:
    new_properties = _merge_object_properties(
        a=a.properties,
        b=b.properties,
    )
    new_required = a.required.union(b.required)
    new_additional_properties = _merge_object_additional_properties(
        a.additional_properties,
        b.additional_properties,
    )
    new_discriminator = _merge_discriminator(
        a.discriminator,
        b.discriminator,
    )
    return model.OASObjectType(
        properties=new_properties,
        required=new_required,
        additional_properties=new_additional_properties,
        discriminator=new_discriminator,
        nullable=_get_value('nullable', a.nullable, b.nullable),
        read_only=_get_value('readOnly', a.read_only, b.read_only),
        write_only=_get_value('writeOnly', a.write_only, b.write_only),
        deprecated=_get_value('deprecated', a.deprecated, b.deprecated),
        default=_get_value('default', a.default, b.default),
        example=_get_value('example', a.example, b.example),
        min_properties=_get_value('minProperties', a.min_properties, b.min_properties),
        max_properties=_get_value('maxProperties', a.max_properties, b.max_properties),
    )


def _merge_discriminator(
        a: t.Optional[model.OASObjectDiscriminator] = None,
        b: t.Optional[model.OASObjectDiscriminator] = None,
) -> t.Optional[model.OASObjectDiscriminator]:
    if a is None and b is None:
        return None
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    elif a is not None and b is not None:
        if a.property_name != b.property_name:
            raise exceptions.OASConflict(
                f'discriminator.propertyName value differs between mixed schemas. '
                f'a={a.property_name} != b={b.property_name}. '
                f'When using "anyOf,oneOf,allOf" '
                f'values in same location must be equal. '
                f'Either make it so or remove one of the duplicating properties.',
            )
        else:
            new_mapping: t.Dict[str, str] = {}
            for prop_name in set(a.mapping.keys()).union(b.mapping.keys()):
                prop_a = a.mapping.get(prop_name)
                prop_b = b.mapping.get(prop_name)
                if prop_a is None and prop_b is None:
                    continue
                elif prop_a is None and prop_b is not None:
                    new_mapping[prop_name] = copy.deepcopy(prop_b)
                elif prop_a is not None and prop_b is None:
                    new_mapping[prop_name] = copy.deepcopy(prop_a)
                elif prop_a is not None and prop_b is not None:
                    if prop_a != prop_b:
                        raise exceptions.OASConflict(
                            f'discriminator.mapping["{prop_name}"] value differs '
                            f'between mixed schemas. '
                            f'a={prop_a} != b={prop_b}. When using "anyOf,oneOf,allOf" '
                            f'values in same location must be equal. '
                            f'Either make it so or remove one of the '
                            f'duplicating properties.',
                        )
                    else:
                        new_mapping[prop_name] = copy.deepcopy(prop_a)
                else:
                    raise Exception('Should not happen')  # pragma: no cover
        return model.OASObjectDiscriminator(
            property_name=copy.copy(a.property_name),
            mapping=new_mapping,
        )
    else:
        raise Exception('Should not happen')  # pragma: no cover


def _merge_object_additional_properties(
        a: t.Union[bool, model.OASType[t.Any]],
        b: t.Union[bool, model.OASType[t.Any]],
) -> t.Union[bool, model.OASType[t.Any]]:
    type_a = type(a)
    type_b = type(b)
    if (type_a, type_b) == (bool, bool):
        return t.cast(bool, _get_value('additionalProperties', a, b))
    elif (type_a, type_b) == (model.OASType[t.Any], model.OASType[t.Any]):
        return merge(a, b)
    else:
        raise exceptions.OASConflict(
            f'additionalProperties value differs between mixed schemas. '
            f'a={type(a)} != b={type(b)}. When using "anyOf,oneOf,allOf" values in '
            f'same location must be equal. '
            f'Either make it so or remove one of the duplicating properties.',
        )


def _merge_object_properties(
        a: t.Optional[t.Dict[str, model.OASType[t.Any]]] = None,
        b: t.Optional[t.Dict[str, model.OASType[t.Any]]] = None,
) -> t.Optional[t.Dict[str, model.OASType[t.Any]]]:
    if a is None and b is None:
        return None
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    elif a is not None and b is not None:
        new_properties: t.Dict[str, model.OASType[t.Any]] = {}

        for prop_name in set(a.keys()).union(b.keys()):
            prop_a = a.get(prop_name)
            prop_b = b.get(prop_name)
            if not (prop_a or prop_b):
                continue
            elif not prop_a and prop_b:
                new_properties[prop_name] = copy.deepcopy(prop_b)
            elif prop_a and not prop_b:
                new_properties[prop_name] = copy.deepcopy(prop_a)
            else:
                new_properties[prop_name] = merge(prop_a, prop_b)

        return new_properties
    else:
        raise Exception('Should not happen')  # pragma: no cover


def _get_value(
        oas_property: str,
        a: t.Optional[V],
        b: t.Optional[V],
) -> t.Optional[V]:
    if (a, b) == (None, None):
        return None
    elif a is None and b is not None:
        return copy.deepcopy(b)
    elif a is not None and b is None:
        return copy.deepcopy(a)
    elif a != b:
        raise exceptions.OASConflict(
            f'{oas_property} value differs between mixed schemas. '
            f'a={a} != b={b}. When using "anyOf,oneOf,allOf" values in '
            f'same location must be equal. '
            f'Either make it so or remove one of the duplicating properties.',
        )
    else:
        return copy.deepcopy(a)
