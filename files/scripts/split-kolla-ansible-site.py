import copy
import os
import re
import yaml

SITEFILE = os.environ.get("SITEFILE", "/repository/ansible/site.yml")
DSTPATH = os.environ.get("DSTPATH", "/ansible")

UNSUPPORTED_ROLES = [
    "baremetal",
    "blazar",
    "ceph",
    "cyborg",
    "freezer",
    "hacluster",
    "ironic",
    "iscsi",
    "kafka",
    "masakari",
    "monasca",
    "monasca_cleanup",
    "murano",
    "opendaylight",
    "qdrouterd",
    "sahara",
    "solum",
    "storm",
    "tacker",
    "telegraf",
    "venus",
    "vitrage",
    "watcher",
    "zookeeper",
]

with open(SITEFILE, "r") as fp:
    site = yaml.load(fp, Loader=yaml.Loader)

group_hosts_based_on_configuration = None
for play in site:
    if "name" not in play:
        continue

    if play["name"] == "Group hosts based on configuration":
        group_hosts_based_on_configuration = play

        for task in play["tasks"]:
            if task["name"] == "Group hosts based on enabled services":
                task["with_items"] = []

for play in site:
    if "name" not in play:
        continue

    if play["name"].startswith("Apply role"):
        name = re.sub(r"\s+", "", play["name"][11:])
        print("PROCESS ROLE %s" % name)

        if name in UNSUPPORTED_ROLES:
            print("ROLE %s IS NOT SUPPORTED" % name)

        else:
            play["gather_facts"] = "false"
            dump = yaml.dump([[play]], Dumper=yaml.Dumper)

            if name == "rabbitmq(outward)":
                name = "rabbitmq-outward"

            local_group_hosts_based_on_configuration = copy.deepcopy(
                group_hosts_based_on_configuration
            )

            local_group_hosts_based_on_configuration["hosts"] = [
                x for x in play["hosts"] if "&enable_" not in x and "_True" not in x
            ]

            with open(os.path.join(DSTPATH, "kolla-%s.yml" % name), "w+") as fp:
                fp.write("---\n")

                for key, value in local_group_hosts_based_on_configuration.items():
                    if key == "tasks" and type(value) == list:  # noqa E721
                        for task in [
                            x
                            for x in value
                            if x["name"] == "Group hosts based on enabled services"
                        ]:
                            if name == "openvswitch":
                                v = "enable_openvswitch_{{ enable_openvswitch | bool }}_enable_ovs_dpdk_{{ enable_ovs_dpdk | bool }}"
                            else:
                                v = f"enable_{name.replace('-', '_')}_{{{{ enable_{name.replace('-', '_')} | bool }}}}"
                            task["with_items"] = v

                dump_group_hosts_based_on_configuration = yaml.dump(
                    [[local_group_hosts_based_on_configuration]], Dumper=yaml.Dumper
                )
                for line in dump_group_hosts_based_on_configuration.splitlines():
                    fp.write(line[2:])
                    fp.write("\n")
                fp.write("\n")

                for line in dump.splitlines():
                    fp.write(line[2:])
                    fp.write("\n")
