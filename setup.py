import os
import sys

import setuptools

__version__ = '0.0.0'
__title__ = 'axion'
__author__ = 'Tomasz Trębski'
__author_email__ = 'kornicameister@gmail.com'
__maintainer__ = __author__
__url__ = 'https://github.com/kornicameister/axion'

if sys.version_info < (3, 6):
    raise RuntimeError(f'{__title__}:{__version__} requires Python 3.6 or greater')

if not any(arg in sys.argv for arg in ['clean', 'check']) and 'SKIP_CYTHON' not in os.environ:
    try:
        from Cython.Build import cythonize
    except ImportError:
        pass
    else:
        compiler_directives = {}

        if 'CYTHON_TRACE' in sys.argv:
            compiler_directives['linetrace'] = True

        os.environ['CFLAGS'] = '-O3'
        ext_modules = cythonize(
            'axion/**/*.py',
            exclude=['axion/mypy.py'],
            nthreads=int(os.getenv('CYTHON_NTHREADS', 0)),
            language_level=3,
            compiler_directives=compiler_directives,
        )

setuptools.setup(
    setup_requires='setupmeta',
    python_requires='>=3.6',
    versioning='post',
    package_data={
        'axion': ['py.typed'],
    },
    zip_safe=False,  # https://mypy.readthedocs.io/en/latest/installed_packages.html
)
