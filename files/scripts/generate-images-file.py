import glob
import re
import os

from ruamel.yaml import YAML
yaml=YAML()

OPENSTACK_VERSION = os.environ.get("OPENSTACK_VERSION", "master")
ROLESPATH = "/repository/ansible/roles"
UNSUPPORTED_ROLES = [
    "baremetal",
    "ceph",
    "certificates",
    "destroy",
    "haproxy-config",
    "nova-hyperv",
    "module-load",
    "opendaylight",
    "prechecks",
    "prune-images",
    "service-cert-copy",
    "service-ks-register",
    "service-stop",
    "services-precheck",
    "stop"  # NOTE: was renamed in stein in service-stop
]

print("---")
print("docker_namespace: osism")
if OPENSTACK_VERSION != "master":
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
        if OPENSTACK_VERSION == "master":
            print("%s_tag: \"{{ repository_version }}\"" % rolename)
        else:
            print("%s_tag: \"{{ docker_openstack_version }}-{{ repository_version }}\"" % rolename)

        tag_is_missing = False
    elif rolename in ['nova-cell']:
        tag_is_missing = False

    for key in [x for x in defaults if x.endswith("_tag") or x.endswith("_image")]:
        if key == "%s_tag" % rolename:
            if tag_is_missing:
                if OPENSTACK_VERSION == "master":
                    print("%s: \"{{ repository_version }}\"" % key)
                else:
                    print("%s: \"{{ docker_openstack_version }}-{{ repository_version }}\"" % key)
        elif key.endswith("_tag"):
            if rolename == "nova-cell":
                if key != "nova_tag":
                    print("%s: \"{{ nova_tag }}\"" % key)
            else:
                print("%s: \"{{ %s_tag }}\"" % (key, rolename))
        elif key.endswith("_image"):
            image = key[:-6].replace("_", "-")
            if image == "openvswitch-db":
                image = "openvswitch-db-server"
            elif image == "placement-api" and OPENSTACK_VERSION in ["queens", "rocky"]:
                image = "nova-placement-api"
            print("%s: \"{{ docker_registry }}/{{ docker_namespace }}/%s\"" % (key, image))
