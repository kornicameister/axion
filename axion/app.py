import typing as t

import typing_extensions as te

from axion import spec


@te.final
class Application:
    __slots__ = (
        'spec',
        'spec_location',
    )

    def __init_subclass__(cls: t.Type['Application']) -> None:
        raise TypeError(
            f'Inheritance class {cls.__name__} from axion.app.Application '
            f'is forbidden',
        )

    def __init__(
            self,
            spec_location: spec.SpecLocation,
    ) -> None:
        self.spec = spec.load(spec_location)
        self.spec_location = spec_location
