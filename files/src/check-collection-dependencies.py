# SPDX-License-Identifier: Apache-2.0

# The collections are installed with --no-deps, so nothing else notices
# when a pinned version starts to depend on a collection that is not
# installed, or on a version of it that is not pinned. Check every
# installed collection's declared dependencies against what is installed.

import glob
import json
import sys

from ansible.galaxy.dependency_resolution.versioning import meets_requirements

COLLECTIONS_PATH = "/usr/share/ansible/collections/ansible_collections"

installed = {}
for manifest in glob.glob(f"{COLLECTIONS_PATH}/*/*/MANIFEST.json"):
    with open(manifest) as fp:
        info = json.load(fp)["collection_info"]
    installed[f"{info['namespace']}.{info['name']}"] = info

errors = []
for name, info in sorted(installed.items()):
    for dependency, requirement in (info.get("dependencies") or {}).items():
        if dependency not in installed:
            errors.append(f"{name} requires {dependency} {requirement}: not installed")
        elif not meets_requirements(installed[dependency]["version"], requirement):
            errors.append(
                f"{name} requires {dependency} {requirement}: "
                f"{installed[dependency]['version']} is installed"
            )

if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
