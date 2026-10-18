# SPDX-License-Identifier: Apache-2.0

# /requirements.txt carries the versions osism/release pins, but kolla-ansible's
# own requirements are installed after it, and uv silently replaces a pinned
# package whose version they exclude. ansible-core is the case that happened:
# stable/2026.1 requires >=2.19, so a 2.18 pin became 2.20 without a trace.
# Check that every package of /requirements.txt still has a version it allows.
#
# A build of a release reads the pins of its release tag, which cannot be
# corrected without moving the tag. VERSION is the tag of this repository,
# e.g. v0.20261011.0 (OSISM 11.0.1), not the OSISM version. The releases up
# to LAST_UNCHECKED_RELEASE were tagged before this check existed, and ten of
# them pin an ansible-core their image never had: the eight 2024.2 releases
# v0.20250530.0 to v0.20251130.0, and v0.20261008.0 and v0.20261011.0
# (OSISM 11.0.0 and 11.0.1). They must stay rebuildable, e.g. to carry a
# security patch, so for them the findings are only a warning. Every other
# build fails: latest, and every new release, whose first and only build is a
# release build.

import os
import re
import sys
from importlib.metadata import PackageNotFoundError, version

from packaging.requirements import Requirement

REQUIREMENTS = "/requirements.txt"
VERSION = os.environ.get("VERSION", "latest")
LAST_UNCHECKED_RELEASE = (0, 20261011, 0)


def unchecked_release(version):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    return bool(match) and tuple(map(int, match.groups())) <= LAST_UNCHECKED_RELEASE


errors = []
with open(REQUIREMENTS) as fp:
    for line in fp:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = version(requirement.name)
        except PackageNotFoundError:
            errors.append(f"{requirement}: not installed")
            continue
        if not requirement.specifier.contains(installed, prereleases=True):
            errors.append(f"{requirement}: {installed} is installed")

if errors:
    print("\n".join(errors), file=sys.stderr)
    if unchecked_release(VERSION):
        print(
            f"Warning only: release {VERSION} was tagged before this check "
            "and keeps the pins of its release tag.",
            file=sys.stderr,
        )
        sys.exit(0)
    print(
        f"A later install replaced packages pinned in {REQUIREMENTS}. Pin a "
        "version the installed kolla-ansible accepts in osism/release "
        "latest/openstack-<series>.yml.",
        file=sys.stderr,
    )
    sys.exit(1)
