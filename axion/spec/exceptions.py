class OASInvalidSpec:
    ...


class OASInvalidTypeValue(OASInvalidSpec, TypeError):
    """OASInvalidTypeValue refers to invalid type of the value.

    Thrown if either "default" or "example" value's type does not match
    the OASType

    """
    ...


class OASInvalidConstraints(OASInvalidSpec, ValueError):
    """OASInvalidConstrains refers to value constraints of the value.

    If, for example, the value's type is "string" and
    "minLength" > "maxLength", this exceptions is thrown.
    """
    ...
