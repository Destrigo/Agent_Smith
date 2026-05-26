"""
Project-level pytest configuration.

Patches tarfile.TarFile.add to strip uid/gid from all tar entries.

Root cause
----------
swebench's copy_to_container() builds a tar archive with tar.add(real_file),
which preserves the host file's uid/gid (e.g. 226785/10102).  Docker's
rootless daemon then tries to lchown the extracted file to that uid inside
the container's user namespace.  Because the host uid is outside the
sub-uid mapping range (/etc/subuid), the kernel rejects the call with
EINVAL → Docker 500 "failed to Lchown … invalid argument".

Fix
---
Zeroing uid/gid on every TarInfo causes Docker to lchown to container-root
(uid 0), which maps correctly in any rootless Docker user-namespace setup.
This conftest.py lives at the project root and is picked up by both the
main test suite and the moulinette test suite (both share the same rootdir).
"""

import tarfile
import pytest


_original_tarfile_add = tarfile.TarFile.add


def _add_strip_ids(self, name, arcname=None, recursive=True, **kwargs):
    """TarFile.add wrapper that zeros uid/gid on every entry."""
    user_filter = kwargs.pop("filter", None)

    def _strip(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        info.gname = "root"
        if user_filter is not None:
            return user_filter(info)
        return info

    return _original_tarfile_add(
        self, name, arcname=arcname, recursive=recursive,
        filter=_strip, **kwargs,
    )


@pytest.fixture(autouse=True, scope="session")
def _patch_tarfile_uid():
    """Strip host uid/gid from tar archives to fix rootless-Docker lchown."""
    tarfile.TarFile.add = _add_strip_ids
    yield
    tarfile.TarFile.add = _original_tarfile_add
