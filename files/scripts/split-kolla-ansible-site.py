# SPDX-License-Identifier: Apache-2.0

import copy
import os
import re
import yaml

SITEFILE = os.environ.get("SITEFILE", "/repository/ansible/site.yml")
DSTPATH = os.environ.get("DSTPATH", "/ansible")

UNSUPPORTED_ROLES = [
    "baremetal",
    "ceph",
    "cyborg",
    "freezer",
    "ironic",
    "iscsi",
    "kafka",
    "mariadb",
    "monasca",
    "monasca_cleanup",
    "murano",
    "nova",
    "opendaylight",
    "qdrouterd",
    "rabbitmq",
    "sahara",
    "solum",
    "storm",
    "tacker",
    "telegraf",
    "venus",
    "vitrage",
    "zookeeper",
]

with open(SITEFILE, "r") as fp:
    site = yaml.load(fp, Loader=yaml.Loader)

group_hosts_based_on_configuration = None
upstream_enable_items = []
for play in site:
    if "name" not in play:
        continue

    if play["name"] == "Group hosts based on configuration":
        group_hosts_based_on_configuration = play

        for task in play["tasks"]:
            if task["name"] == "Group hosts based on enabled services":
                # Keep kolla's own list of enable_* group_by items around: it is
                # the only authoritative record of which enable_* flags actually
                # exist on this release.
                upstream_enable_items = list(task["with_items"])
                task["with_items"] = []


def group_skeleton(value):
    """Reduce a group name or group_by item to a comparable skeleton.

    "enable_ovn_{{ enable_ovn | bool }}" and "enable_ovn_True" both become
    "enable_ovn_<*>", so an item from kolla's list can be matched against a
    group name a play's hosts selector asks for -- including the compound
    "enable_openvswitch_..._enable_ovs_dpdk_..." pair.
    """
    value = re.sub(r"\{\{.*?\}\}", "<*>", value)
    return re.sub(r"True|False", "<*>", value)


def required_enable_items(hosts):
    """kolla's enable_* group_by items that this play's hosts selector needs.

    The prepended "Group hosts based on configuration" play exists only to
    create the enable_<flag>_<bool> groups the role play then intersects with
    ("&enable_ovn_True"), so the hosts selector -- not the role name -- says
    which items to emit. kolla names roles and flags independently: ovn-db and
    ovn-controller both gate on enable_ovn, prometheus-node-exporters on
    enable_prometheus, and cron/logs/kolla_toolbox/prechecks have no flag at
    all. Deriving the name from the role instead invents variables nobody
    defines, and "| bool" on an undefined variable is a hard failure.
    """
    if isinstance(hosts, str):
        hosts = [hosts]

    wanted = [group_skeleton(x[1:]) for x in hosts if x.startswith("&")]
    items = [x for x in upstream_enable_items if group_skeleton(x) in wanted]

    for missing in [x for x in wanted if x not in [group_skeleton(y) for y in items]]:
        print("WARNING: NO enable_* ITEM PROVIDES GROUP %r" % missing)

    return items


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
                            task["with_items"] = required_enable_items(play["hosts"])

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
