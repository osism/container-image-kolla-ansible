# SPDX-License-Identifier: Apache-2.0

# This script writes a list of all existing playbooks to /ansible/playbooks.yml.

from pathlib import Path

import yaml

PREFIX = "kolla"

KEEP_PREFIX = [
    "ceph-rgw",
    "certificates",
    "destroy",
    "facts",
    "gather-facts",
    "prune-images",
    "purge",
    "rgw-endpoint",
    "site",
    "testbed",
    "testbed-identity",
]

HIDE = [
    "blazar",
    "cyborg",
    "freezer",
    "influxdb",
    "kafka",
    "monasca",
    "monasca_cleanup",
    "murano",
    "panko",
    "qdrouterd",
    "rally",
    "sahara",
    "solum",
    "tacker",
    "telegraf",
    "tempest",
    "vitrage",
    "vmtp",
    "watcher",
    "zookeeper",
]

result = {}

for path in Path("/ansible").glob(f"{PREFIX}-*.yml"):
    name = path.with_suffix("").name[len(PREFIX) + 1 :]  # noqa E203

    if name not in HIDE:
        if name in KEEP_PREFIX:
            result[f"{PREFIX}-{name}"] = PREFIX
        else:
            result[name] = PREFIX

with open("/ansible/playbooks.yml", "w+") as fp:
    fp.write(yaml.dump(result))
