# This script removes the role 'common' in the dependencies dictionary
# in the meta/main.yml file from all roles.

import glob

from ruamel.yaml import YAML

yaml = YAML()
yaml.round_trip_loader = True
yaml.round_trip_dumper = True
yaml.explicit_start = True

metafiles = glob.glob("/repository/ansible/roles/**/meta/main.yml", recursive=True)
for metafile in metafiles:
    print(metafile)
    with open(metafile, "r") as fp:
        meta = yaml.load(fp)

    for idx, dependency in enumerate(meta["dependencies"]):
        if dependency["role"] == "common":
            del meta["dependencies"][idx]

    with open(metafile, "w") as fp:
        yaml.dump(meta, fp)
