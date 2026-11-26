import os

from conan.api.output import ConanOutput
from conan.internal.loader import load_python_file
from conan.errors import ConanException, ConanMigrationError
from conan.internal.model.version import Version
from conan.internal.util.files import load, save

CONAN_VERSION = "version.txt"


class Migrator(object):
    def __init__(self, conf_path, current_version):
        self.conf_path = conf_path

        self.current_version = current_version
        self.file_version_path = os.path.join(self.conf_path, CONAN_VERSION)

    def migrate(self):
        try:
            old_version = self._load_old_version()
            if old_version is None or old_version < self.current_version:
                self._apply_migrations(old_version)
                self._update_version_file()
            elif self.current_version < old_version:  # backwards migrations
                ConanOutput().warning(
                    f"Downgrading cache from Conan {old_version} to "
                    f"{self.current_version}"
                )
                self._apply_back_migrations()
                self._update_version_file()
        except Exception as e:
            ConanOutput().error(str(e), error_type="exception")
            raise ConanMigrationError(e)

    def _update_version_file(self):
        try:
            save(self.file_version_path, str(self.current_version))
        except Exception as error:
            raise ConanException(
                "Can't write version file in '{}': {}".format(
                    self.file_version_path, str(error)
                )
            )

    def _load_old_version(self):
        try:
            tmp = load(self.file_version_path)
            old_version = Version(tmp)
        except Exception:
            old_version = None
        return old_version

    def _apply_migrations(self, old_version):
        """
        Apply any migration script.

        :param old_version: ``str`` previous Conan version.
        """
        migrations = os.path.join(self.conf_path, "migrations")
        if not os.path.exists(migrations):
            return

        # Order by versions, and filter only newer than the old_version and up to current CONAN_VERSION
        migration_files = []
        try:
            old_v = Version(old_version) if old_version else None
        except Exception:
            old_v = None
        current_v = Version(CONAN_VERSION)

        for f in os.listdir(migrations):
            if not f.endswith(".py"):
                continue
            version, remain = f.split("_", 1)
            version = Version(version)
            if (old_v is None and version <= current_v) or (
                old_v is not None and version > old_v and version <= current_v
            ):
                migration_files.append((version, remain))
        migration_files = [f"{v}_{r}" for (v, r) in sorted(migration_files)]

        for migration in migration_files:
            ConanOutput().info(f"Applying migration {migration}")
            migration_path = os.path.join(migrations, migration)
            try:
                migrate_module, _ = load_python_file(migration_path)
                migrate_method = migrate_module.migrate
                migrate_method(self.conf_path)
                # Remove the migration after successful application
                os.remove(migration_path)
            except Exception as e:
                ConanOutput().error(
                    f"There was an error running migration: {e}. "
                    f"Recommended to remove the cache and start from scratch",
                    error_type="exception",
                )
                # Keep the migration file for inspection/retry
                continue

    def _apply_back_migrations(self):
        migrations = os.path.join(self.conf_path, "migrations")
        if not os.path.exists(migrations):
            return

        # Order by versions, and filter only newer than the current version
        migration_files = []
        for f in os.listdir(migrations):
            if not f.endswith(".py"):
                continue
            version, remain = f.split("_", 1)
            version = Version(version)
            # Use the instance current_version, not the global conan_version
            if hasattr(self, "current_version") and version > self.current_version:
                migration_files.append((version, remain))
        migration_files = [f"{v}_{r}" for (v, r) in reversed(sorted(migration_files))]

        for migration in migration_files:
            ConanOutput().warning(f"Applying downgrade migration {migration}")
            migration_path = os.path.join(migrations, migration)
            try:
                migrate_module, _ = load_python_file(migration_path)
                migrate_method = migrate_module.migrate
                migrate_method(self.conf_path)
                # Only remove the migration file if it ran successfully
                os.remove(migration_path)
            except Exception as e:
                ConanOutput().error(
                    f"There was an error running downgrade migration: {e}. "
                    f"Recommended to remove the cache and start from scratch",
                    error_type="exception",
                )
                # Do not remove the migration file on failure so it can be inspected or retried
                continue
