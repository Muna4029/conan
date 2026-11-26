import os
import platform
import textwrap

import pytest

from conan.tools.build import cmd_args_to_string
from conan.test.utils.tools import TestClient
from conan.internal.util.files import chdir
from conan.internal.util.runners import detect_runner


@pytest.fixture(scope="module")
def application_folder():
    """
    Instead of relying on an external cmake tool to build a C binary (which may not be
    available in CI), create lightweight Python scripts that print received arguments,
    making the tests self-contained and not dependent on system cmake.
    """
    t = TestClient()
    script = textwrap.dedent("""
    #!/usr/bin/env python3
    import sys
    for arg in sys.argv[1:]:
        print(arg)
    """)
    # Save both a Unix executable and a Windows-named file so tests on either platform
    # can use the created application without requiring cmake.
    t.save({"arg_printer": script, "arg_printer.exe": script})
    # Make the unix script executable when possible
    try:
        os.chmod(os.path.join(t.current_folder, "arg_printer"), 0o755)
        os.chmod(os.path.join(t.current_folder, "arg_printer.exe"), 0o755)
    except Exception:
        # If chmod is not supported on the platform, ignore
        pass

    return t.current_folder


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix console parsing")
@pytest.mark.parametrize("_input, output", [
         (['.', 'foo'], '. foo'),
         (['.', 'foo with sp'], ". 'foo with sp'"),
         (['.', 'foo "with" sp'], ". 'foo \"with\" sp'"),
         (['.', '\'foo with sp\''], '. \'\'"\'"\'foo with sp\'"\'"\'\''),
         (['"."', 'foo'], '\'"."\' foo'),
         (['".', 'foo'], '\'".\' foo'),
])
def test_unix_cases(application_folder, _input, output):
    _input = ["arg_printer"] + _input
    output = "arg_printer {}".format(output)
    assert cmd_args_to_string(_input) == output

    # Check calling the exe that the arguments are the same we tried to input
    with chdir(application_folder):
        _, cmd_parsed_output = detect_runner("./{}".format(output))
        interpreted_args = cmd_parsed_output.splitlines()
        real_args = _input[1:]
        assert real_args == interpreted_args


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Windows", reason="Windows console parsing")
@pytest.mark.parametrize("_input, output", [
         (['.', 'foo'], '. foo'),
         (['"."', '"foo"'], r'\".\" \"foo\"'),
         ([r'\".\"', '"foo"'], r'\\\".\\\" \"foo\"'),
         (['path with spaces/foo', 'var'], '"path with spaces/foo" var'),
         ([r'c:\path with spaces\foo', '%var$:.'], r'"c:\path with spaces\foo" %var$:.'),
])
def test_windows_cases(application_folder, _input, output):
    from subprocess import list2cmdline
    _input = ["arg_printer.exe"] + _input
    output = "arg_printer.exe {}".format(output)
    assert list2cmdline(_input) == output
    assert cmd_args_to_string(_input) == output

    # Check calling the exe that the arguments are the same we tried to input
    with chdir(application_folder):
        _, cmd_parsed_output = detect_runner(output)
        interpreted_args = cmd_parsed_output.splitlines()
        real_args = _input[1:]
        assert real_args == interpreted_args
