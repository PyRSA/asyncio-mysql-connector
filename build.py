# from distutils.command.build_ext import build_ext
# The distutils module is deprecated since Python 3.10.
# See also https://setuptools.pypa.io/en/latest/deprecated/distutils-legacy.html
from setuptools.command.build_ext import build_ext

from Cython.Build import cythonize


def build(setup_kwargs):
    setup_kwargs.update(
        {
            "ext_modules": cythonize(
                [
                    "asyncmy/*.pyx",
                ],
                compiler_directives={"language_level": 3},
            ),
            "cmdclass": {"build_ext": build_ext},
        }
    )
