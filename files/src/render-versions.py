# SPDX-License-Identifier: Apache-2.0

import os

import jinja2
import requests
import yaml

# get environment parameters

VERSION = os.environ.get("VERSION", "latest")
OPENSTACK_VERSION = os.environ.get("OPENSTACK_VERSION", "latest")

# load versions files from release repository

with open("/release/%s/base.yml" % VERSION, "rb") as fp:
    versions = yaml.load(fp, Loader=yaml.FullLoader)

# prepare jinja2 environment

loader = jinja2.FileSystemLoader(searchpath="/src/templates/")
environment = jinja2.Environment(loader=loader)

# render versions.yml

template = environment.get_template("versions.yml.j2")

with open("/release/%s/openstack-%s.yml" % (VERSION, OPENSTACK_VERSION), "rb") as fp:
    versions_openstack = yaml.load(fp, Loader=yaml.FullLoader)

SBOM_URL = f"https://raw.githubusercontent.com/osism/release/main/{VERSION}/sbom-openstack-{OPENSTACK_VERSION}.yml"
r = requests.get(SBOM_URL)

if r.status_code == 200:
    release_versions = yaml.full_load(r.text)
else:
    release_versions = {"versions": {}}

result = template.render(
    {
        "openstack_version": OPENSTACK_VERSION,
        "openstack_previous_version": versions_openstack["openstack_previous_version"],
        "openstackclient_version": versions_openstack["docker_images"][
            "openstackclient"
        ],
        "versions": release_versions["versions"],
    }
)

with open("/ansible/group_vars/all/versions.yml", "w+") as fp:
    fp.write(result)

# render motd

template = environment.get_template("motd.j2")
result = template.render({"manager_version": versions["manager_version"]})
with open("/etc/motd", "w+") as fp:
    fp.write(result)
