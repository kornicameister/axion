from configparser import ConfigParser
from pathlib import Path

from mypy.options import Options


class OASPluginConfig:
    __slots__ = ('oas_dirs', )

    def __init__(self, options: Options) -> None:
        if options.config_file is None:  # pragma: no cover
            return

        plugin_config = ConfigParser()
        plugin_config.read(options.config_file)

        self.oas_dirs = [
            Path(rd) for rd in plugin_config.get(
                'axion-mypy',
                'oas_directories',
                fallback='',
            ).split(',')
        ]
