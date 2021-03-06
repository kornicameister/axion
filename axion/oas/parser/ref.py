import typing as t

from loguru import logger

__all__ = ('resolve', )


def resolve(
    components: t.Dict[str, t.Any],
    ref: t.Optional[str] = None,
) -> t.Dict[str, t.Any]:
    raw_schema: t.Dict[str, t.Any] = {}
    while ref is not None:
        _, component, name = ref.replace('#/', '').split('/')
        logger.trace(
            'Following ref component="{component}" with name="{name}"',
            component=component,
            name=name,
        )
        raw_schema = components[component][name]
        if '$ref' in raw_schema:
            ref = raw_schema['$ref']
        elif isinstance(raw_schema, dict):
            break
    return raw_schema
