import os
import platform
import re
import shutil
import subprocess

import pytest


# Provide a lightweight pytest.mark.tool shim when the test environment does not
# register the marker that enforces external tools. This shim will skip tests
# when the required tools (and simple version checks for cmake) are not
# available, avoiding pytest setup aborts in CI environments without those
# tools.
def _check_version(tool, required_version):
    try:
        if tool == "cmake":
            out = subprocess.check_output(
                [tool, "--version"], stderr=subprocess.STDOUT, universal_newlines=True
            )
            m = re.search(r"cmake version (\d+(?:\.\d+)*)", out)
            if m:
                installed = m.group(1).split(".")
                required = required_version.split(".")
                for i in range(max(len(installed), len(required))):
                    inst_v = int(installed[i]) if i < len(installed) else 0
                    req_v = int(required[i]) if i < len(required) else 0
                    if inst_v > req_v:
                        return True
                    if inst_v < req_v:
                        return False
                return True
    except Exception:
        return False
    return False


def _has_tool(tool):
    return shutil.which(tool) is not None


if not hasattr(pytest.mark, "tool"):

    def tool(*args):
        # args can be like ("cmake",) or ("cmake","3.19") or ("mingw64",)
        it = iter(args)
        for a in it:
            if _has_tool(a):
                # check next for version if present and looks like version
                try:
                    nxt = next(it)
                    if re.match(r"^\d+(\.\d+)*$", nxt):
                        if not _check_version(a, nxt):
                            return pytest.mark.skip(
                                reason=f"Required '{a}' tool version '{nxt}' is not available"
                            )
                        # version satisfied, continue
                    else:
                        # nxt seems like another tool name; verify it now
                        if not _has_tool(nxt):
                            return pytest.mark.skip(
                                reason=f"Required '{nxt}' tool is not available"
                            )
                except StopIteration:
                    pass
            else:
                # tool missing, maybe next arg is a version string or next tool
                try:
                    nxt = next(it)
                    if re.match(r"^\d+(\.\d+)*$", nxt):
                        return pytest.mark.skip(
                            reason=f"Required '{a}' tool version '{nxt}' is not available"
                        )
                    else:
                        return pytest.mark.skip(
                            reason=f"Required '{a}' tool is not available"
                        )
                except StopIteration:
                    return pytest.mark.skip(
                        reason=f"Required '{a}' tool is not available"
                    )
        # all checks passed, return a no-op decorator
        return lambda obj: obj

    pytest.mark.tool = tool

from conan.test.utils.mocks import ConanFileMock
from conan.tools.env.environment import environment_wrap_command
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def editable_cmake(generator, build_folder=None):
    c = TestClient()
    if generator is not None:
        c.save_home(
            {"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)}
        )
    with c.chdir("dep"):
        c.run("new cmake_lib -d name=dep -d version=0.1")
    with c.chdir("pkg"):
        c.run("new cmake_exe -d name=pkg -d version=0.1 -d requires=dep/0.1")

    output_folder = '--output-folder="{}"'.format(build_folder) if build_folder else ""

    def build_dep():
        c.run("build . {}".format(output_folder))
        c.run("build . -s build_type=Debug {}".format(output_folder))

    with c.chdir("dep"):
        c.run("editable add . {}".format(output_folder))
        build_dep()

    def build_pkg(msg, build_editable=False):
        build_editable = "--build=editable" if build_editable else ""
        c.run(f"build . {build_editable}")
        folder = os.path.join("build", "Release")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "pkg/0.1: Hello World Release!" in c.out
        assert "{}: Hello World Release!".format(msg) in c.out
        c.run(f"build . -s build_type=Debug {build_editable}")
        folder = os.path.join("build", "Debug")
        c.run_command(os.sep.join([".", folder, "pkg"]))
        assert "pkg/0.1: Hello World Debug!" in c.out
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install . ")
        c.run("install . -s build_type=Debug")
        build_pkg("dep/0.1")

    # Do a source change in the editable!
    with c.chdir("dep"):
        f = c.load("src/dep.cpp")
        f = f.replace("dep/0.1", "SUPERDEP/0.1")
        c.save({"src/dep.cpp": f})
        build_dep()

    with c.chdir("pkg"):
        build_pkg("SUPERDEP/0.1")

    # Do a source change in the editable, but do NOT build yet
    with c.chdir("dep"):
        f = c.load("src/dep.cpp")
        f = f.replace("SUPERDEP/0.1", "MEGADEP/0.1")
        c.save({"src/dep.cpp": f})
    # And build with --build=editable
    with c.chdir("pkg"):
        build_pkg("MEGADEP/0.1", build_editable=True)

    # Check that create is still possible
    c.run("editable remove dep")
    c.run("create dep")
    c.run("create pkg")
    # print(c.out)
    assert "pkg/0.1: Created package" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool("mingw64")
def test_editable_cmake_windows(generator):
    editable_cmake(generator)


@pytest.mark.tool("cmake")
def test_editable_cmake_windows_folders():
    build_folder = temp_folder()
    editable_cmake(generator=None, build_folder=build_folder)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
@pytest.mark.tool("cmake", "3.19")
def test_editable_cmake_linux(generator):
    editable_cmake(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool("cmake", "3.23")
def test_editable_cmake_osx(generator):
    editable_cmake(generator)


def editable_cmake_exe(generator):
    c = TestClient()
    if generator is not None:
        c.save_home(
            {"global.conf": "tools.cmake.cmaketoolchain:generator={}".format(generator)}
        )

    c.run("new cmake_exe -d name=dep -d version=0.1 -o=dep")

    def build_dep():
        c.run("build .")
        c.run("build . -s build_type=Debug")

    with c.chdir("dep"):
        c.run("editable add .")
        build_dep()

    def run_pkg(msg):
        host_arch = c.get_default_host_profile().settings["arch"]
        cmd_release = environment_wrap_command(
            ConanFileMock(), f"conanrunenv-release-{host_arch}", c.current_folder, "dep"
        )
        c.run_command(cmd_release)
        assert "{}: Hello World Release!".format(msg) in c.out
        cmd_release = environment_wrap_command(
            ConanFileMock(), f"conanrunenv-debug-{host_arch}", c.current_folder, "dep"
        )
        c.run_command(cmd_release)
        assert "{}: Hello World Debug!".format(msg) in c.out

    with c.chdir("pkg"):
        c.run("install --requires=dep/0.1")
        c.run("install --requires=dep/0.1 -s build_type=Debug")
        run_pkg("dep/0.1")

    # Do a source change in the editable!
    with c.chdir("dep"):
        dep = c.load("src/dep.cpp")
        dep = dep.replace("dep/0.1", "SUPERDEP/0.1")
        c.save({"src/dep.cpp": dep})
        build_dep()

    with c.chdir("pkg"):
        run_pkg("SUPERDEP/0.1")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
@pytest.mark.parametrize("generator", [None, "MinGW Makefiles"])
@pytest.mark.tool("mingw64")
def test_editable_cmake_windows_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("generator", [None, "Ninja", "Ninja Multi-Config"])
@pytest.mark.tool("cmake", "3.19")
def test_editable_cmake_linux_exe(generator):
    editable_cmake_exe(generator)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
@pytest.mark.parametrize("generator", [None, "Ninja", "Xcode"])
@pytest.mark.tool("cmake", "3.23")
def test_editable_cmake_osx_exe(generator):
    editable_cmake_exe(generator)
