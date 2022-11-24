import os
import sys
import re
import platform
from numpy.lib.utils import get_include as np_get_include

from setuptools import setup
from distutils.extension import Extension

gitdir = os.path.join(os.path.dirname(__file__), '.git')
__version__ = None
with open('pytrms/_version.py', 'r') as f:
    exec(f.read())

print('using version:', __version__)

with open('doc/index.rst', 'r') as f:
    eof_marker = ".. toctree::"
    long_description = ''
    for line in f:
        if line.startswith(eof_marker):
            break
        long_description += line

if '64' in platform.python_compiler():
    arch = 'x64'
    program_files = os.getenv('ProgramFiles')
else:
    arch = 'x86'
    program_files = os.getenv('ProgramFiles(x86)')

if not os.path.exists(os.path.join(program_files, 'National Instruments/Shared/LabVIEW Run-Time')):
    print('Warning: Did not find National Instruments LabView Run-Time on this system! '
          'This means part of this Python package will not work. '
          'Do you want to continue?')
    if not input('Yes/No?').lower().startswith('y'):
        sys.exit()

packages = [
    'pytrms',
]

install_requires = [
    'h5py>=3.6,<4.0',
    'requests>=2.27.1,<3.0',
    'pandas>=1.4.0,<2.0',
    'pyModbusTCP>=0.2,<0.3',
]

extra_compile_args = [
    # '/DDEBUG',
]

extensions=[
    Extension('icapi',
              ['src/icapimodule.c'],
              libraries=['IcAPI_c_%s' % arch],
              library_dirs=['lib/'],
              include_dirs=[
                  'include',
                  np_get_include(),
                  ],
              extra_compile_args=extra_compile_args,
              ),
]

package_data = {
    'pytrms': [
        '../par_ID_list.txt',
        'data/IoniTofPrefs.ini',
    ],
}

setup_kwargs = {
    'name': 'pytrms',
    'version': __version__,
    'description': 'Python bundle for proton-transfer reaction mass-spectrometry (PTR-MS).',
    'long_description': long_description,
    'long_description_content_type': 'text/x-rst',
    'author': 'Moritz Koenemann',
    'author_email': 'moritz.koenemann@ionicon.com',
    'url': 'https://www.ionicon.com/',
    'packages': packages,
    'package_data': package_data,
    'ext_modules': extensions,
    'install_requires': install_requires,
    'python_requires': '>=3.8,<4.0',
}


if __name__ == '__main__':
    setup(**setup_kwargs)
