# NOTE: This is a quick workaround.
#
# This script reads the file 99-overwrite in the /ansible/inventory directory (if it exists).
#
# Then it reads all other files in /ansible/inventory and removes from them all sections that
# are present in 99-overwrite. It considers the variant with :children and without.
#
# With this approach it is now possible to completely overwrite all group definitions from
# existing files via the 99-overwrite file.

import configparser
import os
import sys

dirname = '/ansible/inventory/'
filename = '99-overwrite'

if not os.path.isfile(os.path.join(dirname, filename)):
    sys.exit(0) 

config = configparser.ConfigParser(allow_no_value=True, delimiters='=')
config.read(os.path.join(dirname, filename))

sections = []

for section in config.sections():
    if section.endswith(':children'):
        sections.append(section[:-9])
    else:
        sections.append("%s:children" % section)

    sections.append(section)

for f in os.scandir(dirname):
    if f.is_file() and not f.path.endswith(filename):
        changed = False

        config = configparser.ConfigParser(allow_no_value=True, delimiters='=')
        config.read(os.path.join(f))

        for section in sections:
            if config.remove_section(section):
                changed = True
        
        if changed:
            with open(f, 'w') as fp:
                config.write(fp)
