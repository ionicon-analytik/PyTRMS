import setuptools
from setuptools.extension import Extension
from numpy.lib.utils import get_include as np_get_include
from Cython.Distutils import build_ext

import platform
import os
import sys
import shutil

if '64' in platform.python_compiler():
    arch = 'x64'
    program_files = os.getenv('ProgramFiles')
else:
    arch = 'x86'
    program_files = os.getenv('ProgramFiles(x86)')

# -----------------------------------------------------------------------------

extensions=[
    Extension('icapi',
        [
            'src/icapimodule.c'
        ],
        libraries=[
            'IcAPI_c_%s' % arch
        ],
        library_dirs=[
            'lib/'
        ],
        include_dirs=[
            'include',
            np_get_include(),
        ],
        extra_compile_args=[
                # '/DDEBUG',
            #com_args = ['-std=c99', '-O3', '-fopenmp']
        ],
    ),
]

# -----------------------------------------------------------------------------

class BuildExt(build_ext):
    def build_extensions(self):
        try:
            super().build_extensions()
        except Exception:
            pass

def build(setup_kwargs):
    setup_kwargs.update(
        dict(
            cmdclass=dict(build_ext=BuildExt),
            ext_modules=extensions,
            zip_safe=False,
        )
    )
    setuptools.setup(**setup_kwargs)

# -----------------------------------------------------------------------------

if not os.path.exists(os.path.join(program_files, 'National Instruments/Shared/LabVIEW Run-Time')):
    print('Warning: Did not find National Instruments LabView Run-Time on this system! '
          'This means part of this Python package will not work. '
          'Do you want to continue?')
    if not input('Yes/No?').lower().startswith('y'):
        sys.exit()

setup_kwargs = {
        # seems like running build_ext
        # doesn't need any meta-info..
}

if __name__ == '__main__':
    build(setup_kwargs)
    print('build succeeded! copying', 
        shutil.copy2(
            'build/lib.win-amd64-cpython-38/icapi.cp38-win_amd64.pyd',
            '.'
        ),
        'to root directory')

