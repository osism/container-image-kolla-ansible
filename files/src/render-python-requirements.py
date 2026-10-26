# SPDX-License-Identifier: Apache-2.0

# /requirements.txt carries the versions osism/release pins. It is installed in
# the same resolver run as kolla-ansible, so a pin that kolla-ansible's own
# requirements exclude fails the build.
#
# A build of a release reads the pins of its release tag, which cannot be
# corrected without moving the tag. VERSION is the tag of this repository,
# e.g. v0.20261011.0 (OSISM 11.0.1), not the OSISM version. Releases up to
# LAST_UNCHECKED_RELEASE were built by installing kolla-ansible after
# /requirements.txt, which replaced such a pin without a trace: several 2024.2
# and 2026.1 releases pin an ansible-core their image never had. They must stay
# rebuildable, e.g. to carry a security patch, so for them a pin that
# kolla-ansible excludes is dropped with a warning, and the resolver picks the
# version kolla-ansible allows, as their original builds did.

import os
import re
import sys

import jinja2
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# get environment parameters

OPENSTACK_VERSION = os.environ.get("OPENSTACK_VERSION", "master")
VERSION = os.environ.get("VERSION", "latest")

LAST_UNCHECKED_RELEASE = (0, 20261011, 0)
UPSTREAM_REQUIREMENTS = "/repository/requirements.txt"


def unchecked_release(version):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    return bool(match) and tuple(map(int, match.groups())) <= LAST_UNCHECKED_RELEASE


def requirements(lines):
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if line:
            yield Requirement(line)


def excluded_pins(lines):
    with open(UPSTREAM_REQUIREMENTS) as fp:
        upstream = [
            requirement
            for requirement in requirements(fp)
            if not requirement.marker or requirement.marker.evaluate()
        ]
    for requirement in requirements(lines):
        pins = [s.version for s in requirement.specifier if s.operator == "=="]
        for other in upstream:
            if canonicalize_name(other.name) != canonicalize_name(requirement.name):
                continue
            if any(not other.specifier.contains(pin, prereleases=True) for pin in pins):
                yield str(requirement), str(other)


# load versions files from release repository

with open("/release/latest/base.yml", "rb") as fp:
    versions = yaml.load(fp, Loader=yaml.FullLoader)

with open("/release/latest/openstack-%s.yml" % OPENSTACK_VERSION, "rb") as fp:
    openstack_versions = yaml.load(fp, Loader=yaml.FullLoader)

# prepare jinja2 environment

loader = jinja2.FileSystemLoader(searchpath="/src/templates/")
environment = jinja2.Environment(loader=loader)

# render requirements.txt

template = environment.get_template("requirements.txt.j2")
result = template.render(
    {
        "ansible_version": openstack_versions["ansible_version"],
        "ansible_core_version": openstack_versions["ansible_core_version"],
        "osism_projects": versions["osism_projects"],
        "version": VERSION,
    }
)

if unchecked_release(VERSION):
    lines = result.splitlines(keepends=True)
    dropped = dict(excluded_pins(lines))
    for pin, upstream in dropped.items():
        print(
            f"Warning: release {VERSION} pins {pin}, which kolla-ansible's "
            f"{upstream} excludes; dropping the pin.",
            file=sys.stderr,
        )
    result = "".join(
        line
        for line in lines
        if not any(str(requirement) in dropped for requirement in requirements([line]))
    )

with open("/requirements.txt", "w+") as fp:
    fp.write(result)
