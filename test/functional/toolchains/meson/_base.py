import platform
import re
import subprocess
import unittest

import pytest

from conan.test.utils.tools import TestClient


def _get_gcc_major_version():
    """Get the GCC major version dynamically."""
    try:
        result = subprocess.run(['gcc', '-dumpversion'], capture_output=True, text=True, check=False)
        version = result.stdout.strip()
        return version.split('.')[0]
    except OSError:
        return None


def _get_clang_major_version():
    """Get the clang major version dynamically."""
    try:
        result = subprocess.run(['clang', '--version'], capture_output=True, text=True, check=False)
        # Output format: "Apple clang version 17.0.0 (clang-1700.6.3.2)" or "clang version 13.0.0"
        version_line = result.stdout.split('\n')[0]
        match = re.search(r'clang(?: version)? (\d+)', version_line)
        if match:
            return match.group(1)
        return None
    except OSError:
        return None


def _get_msvc_version():
    """Get the MSVC version major number dynamically."""
    try:
        # Try to get MSVC version from environment or cl.exe
        result = subprocess.run(['cl'], capture_output=True, text=True, check=False)
        # MSVC version format: "Microsoft (R) C/C++ Optimizing Compiler Version 19.34.31912 for x64"
        match = re.search(r'Version (\d+)', result.stderr if result.stderr else result.stdout)
        if match:
            return match.group(1)
        return None
    except OSError:
        return None


@pytest.mark.tool("meson")
@pytest.mark.skipif(platform.system() not in ("Darwin", "Windows", "Linux"),
                    reason="Not tested for not mainstream boring operating systems")
class TestMesonBase(unittest.TestCase):
    def setUp(self):
        self.t = TestClient()

    def _check_binary(self):
        # FIXME: Some values are hardcoded to match the CI setup
        host_arch = self.t.get_default_host_profile().settings['arch']
        arch_macro = {
            "gcc": {"armv8": "__aarch64__", "x86_64": "__x86_64__"},
            "msvc": {"armv8": "_M_ARM64", "x86_64": "_M_X64"}
        }
        if platform.system() == "Darwin":
            self.assertIn(f"main {arch_macro['gcc'][host_arch]} defined", self.t.out)
            self.assertIn("main __apple_build_version__", self.t.out)
            clang_major = _get_clang_major_version()
            if clang_major:
                self.assertIn(f"main __clang_major__{clang_major}", self.t.out)
            else:
                # Fallback to the original hardcoded value if we can't detect clang version
                self.assertIn("main __clang_major__15", self.t.out)
            # TODO: check why __clang_minor__ seems to be not defined in XCode 12
            # commented while migrating to XCode12 CI
            # self.assertIn("main __clang_minor__0", self.t.out)
        elif platform.system() == "Windows":
            self.assertIn(f"main {arch_macro['msvc'][host_arch]} defined", self.t.out)
            msvc_ver = _get_msvc_version()
            if msvc_ver:
                self.assertIn(f"main _MSC_VER{msvc_ver}", self.t.out)
            else:
                # Fallback to the original hardcoded value if we can't detect MSVC version
                self.assertIn("main _MSC_VER19", self.t.out)
            self.assertIn("main _MSVC_LANG2014", self.t.out)
        elif platform.system() == "Linux":
            self.assertIn(f"main {arch_macro['gcc'][host_arch]} defined", self.t.out)
            gcc_major = _get_gcc_major_version()
            if gcc_major:
                self.assertIn(f"main __GNUC__{gcc_major}", self.t.out)
            else:
                # Fallback to the original hardcoded value if we can't detect GCC version
                self.assertIn("main __GNUC__9", self.t.out)
