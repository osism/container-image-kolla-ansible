import os

import jinja2
import yaml

# get environment parameters

OPENSTACK_VERSION = os.environ.get("OPENSTACK_VERSION", "master")
VERSION = os.environ.get("VERSION", "latest")

# load versions files from release repository

with open("/release/%s/base.yml" % VERSION, "rb") as fp:
    versions = yaml.load(fp, Loader=yaml.FullLoader)

with open("/release/%s/openstack-%s.yml" % (VERSION, OPENSTACK_VERSION), "rb") as fp:
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
with open("/requirements.txt", "w+") as fp:
    fp.write(result)
