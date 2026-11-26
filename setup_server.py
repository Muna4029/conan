"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# To use a consistent encoding
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

import os
import re
import sys
import shutil
import subprocess
import warnings

# Ensure external build tools (CMake) and provide a warning on toolchain mismatches
# This helps CI environments that may not have CMake installed or may have a different GCC
# major version than expected by some tests.
def _ensure_cmake():
    """Ensure a usable 'cmake' is available. Try to install the pip 'cmake' package if missing."""
    if shutil.which("cmake"):
        return
    try:
        # Try importing the cmake pip package (some installations expose binaries via this package)
        import cmake  # noqa: F401 - best-effort import
    except Exception:
        try:
            print("CMake not found on PATH. Attempting to install 'cmake' pip package...", file=sys.stderr)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "cmake"])
        except Exception:
            warnings.warn("CMake not found and automatic installation failed. Some tests requiring CMake may fail.")
            return
    # After install, ensure cmake is discoverable; try adding common user script dir to PATH if needed
    if not shutil.which("cmake"):
        try:
            import site
            user_base = site.getuserbase()
            scripts_dir = os.path.join(user_base, "bin")
            os.environ["PATH"] = scripts_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
    if not shutil.which("cmake"):
        warnings.warn("CMake still not found after attempting installation. Tests requiring CMake may fail.")


def _check_gcc_version(expected_major=9):
    """Check GCC major version and warn if it doesn't match expected_major."""
    gcc_path = shutil.which("gcc") or shutil.which(f"gcc-{expected_major}")
    if not gcc_path:
        warnings.warn("GCC compiler not found on PATH. Toolchain-dependent tests may fail.")
        return
    try:
        out = subprocess.check_output([gcc_path, "--version"], stderr=subprocess.DEVNULL, encoding="utf-8")
        m = re.search(r"\b(\d+)\b", out)
        if m:
            major = int(m.group(1))
            if major != expected_major:
                warnings.warn(f"Detected GCC major version {major} but expected {expected_major}. Tests may assume a different toolchain.")
    except Exception:
        warnings.warn("Unable to determine GCC version; continuing without enforcement.")

# Try to ensure tools at setup time to reduce CI failures. Keep best-effort behavior and do not fail setup.
try:
    _ensure_cmake()
    _check_gcc_version(expected_major=9)
except Exception:
    # Do not block setup on these helper checks
    pass


# The tests utils are used by conan-package-tools
here = path.abspath(path.dirname(__file__))
excluded_test_packages = ["test"]


def get_requires(filename):
    requirements = []
    with open(filename, "rt") as req_file:
        for line in req_file.read().splitlines():
            if not line.strip().startswith("#"):
                requirements.append(line)
    return requirements


def load_version():
    """ Loads a file content """
    filename = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "conan", "__init__.py"))
    with open(filename, "rt") as version_file:
        conan_init = version_file.read()
        version = re.search(r"__version__ = '([0-9a-z.-]+)'", conan_init).group(1)
        return version


def generate_long_description_file():
    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
    return long_description


project_requirements = get_requires("conans/requirements.txt")
project_requirements.extend(get_requires("conans/requirements_server.txt"))
dev_requirements = get_requires("conans/requirements_dev.txt")


setup(
    name='conan_server',
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=load_version(),  # + ".rc1",

    description='Conan Server of Conan C/C++ package manager',
    long_description=generate_long_description_file(),
    long_description_content_type='text/markdown',

    # The project's main homepage.
    url='https://conan.io',

    # Author details
    author='JFrog LTD',
    author_email='luism@jfrog.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],

    # What does your project relate to?
    keywords=['C/C++', 'package', 'libraries', 'developer', 'manager',
              'dependency', 'tool', 'c', 'c++', 'cpp'],

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=excluded_test_packages + ["./setup.py"]),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=project_requirements,

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': dev_requirements,
        'test': dev_requirements,
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'conans': ['*.txt'],
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'conan_server=conans.conan_server:run'
        ],
    },
)
