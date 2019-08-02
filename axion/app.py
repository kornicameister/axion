from axion import spec


class Application:
    __slots__ = ('spec')

    def __init__(
            self,
            spec_location: spec.SpecLocation,
    ) -> None:
        self.spec = spec.load(spec_location)  # type: spec.Spec
