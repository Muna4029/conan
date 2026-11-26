import os

import fasteners

from conan.internal.errors import NotFoundException
from conan.internal.util.files import rmdir
from conans.server.utils.files import relative_dirs


class ServerDiskAdapter:
    """Manage access to disk files with common methods required
    for conan operations"""

    def __init__(self, base_url, base_storage_path):
        """
        :param base_url Base url for generate urls to download and upload operations"""

        self.base_url = base_url
        # URLs are generated removing this base path
        self._store_folder = base_storage_path

    def get_file_list(self, absolute_path=""):
        # Treat absolute_path as store-relative. Build the full filesystem path
        full_path = (
            os.path.normpath(os.path.join(self._store_folder, absolute_path))
            if absolute_path
            else self._store_folder
        )
        if not self.path_exists(full_path):
            raise NotFoundException("Path not found: %s" % full_path)
        paths = relative_dirs(full_path)
        # Return store-relative paths (not absolute filesystem paths)
        rel_root = absolute_path or ""
        result = []
        for relpath in paths:
            joined = os.path.normpath(os.path.join(rel_root, relpath))
            # Ensure no leading separator to keep paths relative to the store
            if joined.startswith(os.sep):
                joined = joined.lstrip(os.sep)
            result.append(joined)
        return result

    def delete_folder(self, path):
        """Delete folder from disk. Path is interpreted relative to the store folder unless an absolute path is provided."""
        full_path = (
            os.path.normpath(os.path.join(self._store_folder, path))
            if not os.path.isabs(path)
            else path
        )
        if not self.path_exists(full_path):
            raise NotFoundException("Path not found: %s" % full_path)
        rmdir(full_path)

    def path_exists(self, path, base=None):
        """Check existence of a path. If base is provided, treat path as relative to base."""
        if base:
            full = os.path.join(base, path)
        else:
            full = path
        return os.path.exists(full)

    def read_file(self, path, lock_file):
        with fasteners.InterProcessLock(lock_file):
            # Explicitly specify encoding to avoid environment-dependent defaults
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    def write_file(self, path, contents, lock_file):
        with fasteners.InterProcessLock(lock_file):
            # Ensure parent directory exists and write with a defined encoding
            dirpath = os.path.dirname(path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(contents)
