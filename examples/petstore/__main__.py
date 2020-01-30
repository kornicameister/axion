from pathlib import Path

import axion

ax = axion.Axion(
    Path.cwd(),
    'aiohttp',
    configuration=axion.Configuration(),
)
ax.add_api(spec_location=Path('openapi.yml'))
