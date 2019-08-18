import typing as t

from loguru import logger
import yarl

from axion import specification


def make(servers: t.List[specification.OASServer]) -> str:
    server_count = len(servers)
    if server_count > 1:
        logger.warning(
            (
                'There are {count} servers, axion will assume first one. '
                'This behavior might change in the future, once axion knows '
                'how to deal with multiple servers'
            ),
            count=len(servers),
        )
    first_server = servers[0]
    logger.debug(
        'Computing base path using server definition = {server}',
        server=first_server,
    )
    the_base_path = yarl.URL(first_server.url.format(**first_server.variables)).path

    logger.info(
        'API base path will be {base_path}',
        base_path=the_base_path,
    )

    return the_base_path
