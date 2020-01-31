import glob
import re
import os

from ruamel.yaml import YAML
yaml=YAML()

OPENSTACK_VERSION = os.environ.get("OPENSTACK_VERSION", "rocky")
ROLESPATH = "/repository/ansible/roles"
UNSUPPORTED_ROLES = [
    "baremetal",
    "ceph",
    "certificates",
    "destroy",
    "nova-hyperv",
    "opendaylight",
    "prechecks",
    "service-stop",
    "stop"  # NOTE(berendt): was renamed in stein in service-stop
]

print("---")
print("docker_namespace: osism")
print("docker_openstack_version: %s" % OPENSTACK_VERSION)

for rolepath in glob.glob("%s/*" % ROLESPATH):
    if os.path.basename(rolepath) in UNSUPPORTED_ROLES or not os.path.isdir(rolepath):
        continue

    rolename = os.path.basename(rolepath)

    # NOTE(berendt): workaround for https://review.opendev.org/693058
    defaults_filename = "main.yaml" if (rolename == "module-load" and OPENSTACK_VERSION != "master") else "main.yml"

    with open(os.path.join(rolepath, "defaults", defaults_filename)) as fp:
        defaults = yaml.load(fp)

    if rolename == "ovs-dpdk":
        rolename = "ovsdpdk"

    print("\n" + "#" * 30)
    print("# role: %s\n" % rolename)

    tag_is_missing = True
    if rolename in ['panko', 'skydive', 'common', 'freezer']:
        print("%s_tag: \"{{ docker_openstack_version }}-{{ repository_version }}\"" % rolename)
        tag_is_missing = False

    for key in [x for x in defaults if x.endswith("_tag") or x.endswith("_image")]:
        if key == "%s_tag" % rolename:
            if tag_is_missing:
                print("%s: \"{{ docker_openstack_version }}-{{ repository_version }}\"" % key)
        elif key.endswith("_tag"):
            print("%s: \"{{ %s_tag }}\"" % (key, rolename))
        elif key.endswith("_image"):
            image = key[:-6].replace("_", "-")
            if image == "openvswitch-db":
                image = "openvswitch-db-server"
            elif image == "placement-api":
                image = "nova-placement-api"
            print("%s: \"{{ docker_registry }}/{{ docker_namespace }}/%s\"" % (key, image))
