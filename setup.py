import sys

import setuptools

__title__ = 'axion'
__author__ = 'Tomasz Trębski'
__author_email__ = 'kornicameister@gmail.com'
__maintainer__ = __author__
__url__ = f'https://github.com/kornicameister/{__title__}'

if sys.version_info < (3, 6):
    raise RuntimeError(f'{__title__} requires Python 3.6 or greater')

setuptools.setup(
    setup_requires='setupmeta',
    versioning='post',
)
