# (c) 2016, Matt Martz <matt@sivel.net>
# (c) 2017 Ansible Project
# (c) 2023 Christian Berendt <berendt@osism.tech>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json

from ansible.parsing.ajson import AnsibleJSONEncoder
from ansible.plugins.callback import CallbackBase


__metaclass__ = type

DOCUMENTATION = """
    name: json
    short_description: Outputs summary stats in JSON format on STDERR.
    description:
        - Outputs summary stats in JSON format on STDERR.
    type: aggregate
    requirements: []
    options:
      json_indent:
        name: Use indenting for the JSON output
        description: 'If specified, use this many spaces for indenting in the JSON output. If <= 0, write to a single line.'
        default: 4
        env:
          - name: ANSIBLE_JSON_INDENT
        ini:
          - key: json_indent
            section: defaults
        type: integer
"""


LOCKSTEP_CALLBACKS = frozenset(("linear", "debug"))


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "json_stats"
    CALLBACK_NEEDS_WHITELIST = False
    CALLBACK_NEEDS_ENABLED = False

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display)
        self.set_options()

        self._json_indent = self.get_option("json_indent")
        if self._json_indent <= 0:
            self._json_indent = None

    def playbook_on_stats(self, stats):
        self.v2_playbook_on_stats(stats)

    def v2_playbook_on_stats(self, stats):
        """Display info about playbook statistics"""

        hosts = sorted(stats.processed.keys())

        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s

        result = {"stats": summary}
        self._display.display(
            json.dumps(
                result,
                cls=AnsibleJSONEncoder,
                indent=self._json_indent,
                sort_keys=True,
            ),
            stderr=True,
        )
