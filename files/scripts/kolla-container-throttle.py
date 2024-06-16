# SPDX-License-Identifier: Apache-2.0

# This script adds the throttle argument to all kolla_container tasks
# if they are a handler.

import glob

find = "  kolla_container:"
replace = """  throttle: "{{ kolla_handler_throttle | default(-1) }}"
  kolla_container:"""

handlerfiles = glob.glob(
    "/repository/ansible/roles/**/handlers/main.yml", recursive=True
)
for handlerfile in handlerfiles:
    print(f"PROCESSING {handlerfile}")
    with open(handlerfile, "r") as fp:
        data = fp.read()

    data = data.replace(find, replace)

    with open(handlerfile, "w") as fp:
        fp.write(data)
