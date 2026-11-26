import os

from conan.internal.model.profile import Profile
from conan.internal.util.files import save


def create_profile(folder, name, settings=None, package_settings=None, options=None):
    profile = Profile()
    profile.settings = settings or {}

    # Always set package_settings (even if empty) so it will be serialized/persisted
    profile.package_settings = package_settings or {}

    # Assign options directly (or an empty dict) to ensure predictable serialization
    profile.options = options or {}

    save(os.path.join(folder, name), profile.dumps())
