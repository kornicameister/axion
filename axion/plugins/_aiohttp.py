import typing_extensions as te

from axion import plugin


@te.final
class AioHttpPlugin(plugin.Plugin, version='0.0.1'):
    """aiohttp plugin for axion. """
