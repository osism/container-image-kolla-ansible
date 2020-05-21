import re
import os

import ruamel.yaml

SITEFILE = "/repository/ansible/site.yml"
DSTPATH = "/ansible"

UNSUPPORTED_ROLES = [
    "baremetal",
    "ceph",
    "opendaylight"
]

with open(SITEFILE, "r") as fp:
    site = ruamel.yaml.safe_load(fp)

group_hosts_based_on_configuration = None
for play in site:
    if "name" not in play:
        continue

    if play["name"] == "Group hosts based on configuration":
        group_hosts_based_on_configuration = play
        dump_group_hosts_based_on_configuration = ruamel.yaml.dump([group_hosts_based_on_configuration], Dumper=ruamel.yaml.RoundTripDumper, indent=4, block_seq_indent=2)

for play in site:
    if "name" not in play:
        continue

    if play["name"].startswith("Apply role"):
        name = re.sub(r"\s+", "", play["name"][11:])
        print("PROCESS ROLE %s" % name)

        if name in UNSUPPORTED_ROLES:
            print("ROLE %s IS NOT SUPPORTED" % name)

        else:
            play["gather_facts"] = "no"
            dump = ruamel.yaml.dump([play], Dumper=ruamel.yaml.RoundTripDumper, indent=4, block_seq_indent=2)
            if name == "rabbitmq(outward)":
                name = "rabbitmq-outward"

            with open(os.path.join(DSTPATH, "kolla-%s.yml" % name), "w+") as fp:
                fp.write("---\n")

                if group_hosts_based_on_configuration:
                    for line in dump_group_hosts_based_on_configuration.splitlines():
                        fp.write(line[2:])
                        fp.write("\n")
                    fp.write("\n")

                for line in dump.splitlines():
                    fp.write(line[2:])
                    fp.write("\n")
