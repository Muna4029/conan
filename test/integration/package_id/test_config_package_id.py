import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


@pytest.mark.parametrize("config_version, mode, result", [
    ("myconfig/1.2.3#rev1:pid1#prev1", "minor_mode", "myconfig/1.2.Z"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "patch_mode", "myconfig/1.2.3"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "full_mode", "myconfig/1.2.3#rev1:pid1"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "revision_mode", "myconfig/1.2.3#rev1"),
    ("myconfig/1.2.3", "minor_mode", "myconfig/1.2.Z")])
def test_config_package_id(config_version, mode, result):
    c = TestClient()
    config_version = json.dumps({"config_version": [config_version]})
    save(c.paths.config_version_path, config_version)
    save(c.paths.global_conf_path, f"core.package_id:config_mode={mode}")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    assert f"config_version: {result}" in c.out
    c.run("list pkg/0.1:* --format=json")
    # Use c.out consistently and avoid hardcoded revisions/package-ids
    info = json.loads(c.out)
    revisions = info.get("Local Cache", {}).get("pkg/0.1", {}).get("revisions", {})
    assert revisions, "No revisions found for pkg/0.1 in local cache"
    # pick the first revision available (robust against varying revision hashes)
    rrev = revisions[next(iter(revisions))]
    packages = rrev.get("packages", {})
    assert packages, f"No packages found in revision {list(revisions.keys())[0]}"
    # find a package whose info matches the expected config_version
    pkg = None
    for pid, p in packages.items():
        if p.get("info") == {"config_version": [result]}:
            pkg = p
            break
    if pkg is None:
        # fallback: if only one package exists, use it; otherwise report clearly
        if len(packages) == 1:
            pkg = next(iter(packages.values()))
        else:
            raise AssertionError(f"No package with expected info found for config_version {result}")
    assert pkg.get("info") == {"config_version": [result]}


def test_error_config_package_id():
    c = TestClient()
    c.save_home({"global.conf": "core.package_id:config_mode=minor_mode"})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .", assert_error=True)
    assert "ERROR: core.package_id:config_mode defined, " \
           "but error while loading 'config_version.json'" in c.out

@pytest.mark.parametrize("config_version, mode, result", [
    ("myconfig/1.2.3#rev1:pid1#prev1", "minor_mode", "myconfig/1.2.Z"),
    ("myconfig/1.2.3#rev1:pid1#prev1", "patch_mode", "myconfig/1.2.3"),
])
def test_config_package_id_clear(config_version, mode, result):
    c = TestClient(light=True)
    config_version = json.dumps({"config_version": [config_version]})
    save(c.paths.config_version_path, config_version)
    save(c.paths.global_conf_path, f"core.package_id:config_mode={mode}")
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package_id("self.info.clear()")})
    c.run("create .")
    assert f"config_version: {result}" not in c.out


def test_recipe_revision_mode():
    clienta = TestClient()
    save(clienta.paths.new_config_path, "core.package_id:default_unknown_mode=recipe_revision_mode")

    clienta.save({"conanfile.py": GenConanfile()})
    clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")

    clientb = TestClient(cache_folder=clienta.cache_folder)
    clientb.save({"conanfile.py": GenConanfile("libb", "0.1").with_require("liba/0.1@user/testing")})
    clientb.run("create . --user=user --channel=testing")

    clientc = TestClient(cache_folder=clienta.cache_folder)
    clientc.save({"conanfile.py": GenConanfile("libc", "0.1").with_require("libb/0.1@user/testing")})
    clientc.run("install . --user=user --channel=testing")

    # Do a minor change to the recipe, it will change the recipe revision
    clienta.save({"conanfile.py": str(GenConanfile()) + "# comment"})
    clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")

    clientc.run("install . --user=user --channel=testing", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'libb/0.1@user/testing'" in clientc.out
    # Building b with the new recipe revision of liba works
    clientc.run("install . --user=user --channel=testing --build=libb*")

    # Now change only the package revision of liba
    clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")
    clientc.run("install . --user=user --channel=testing")
