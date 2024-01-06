#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0

# NOTE: This is a first step to make Ansible Vault usable via OSISM workers.
#       It's not ready in that form yet.

import os

from cryptography.fernet import Fernet
from redis import Redis

keyfile = "/share/ansible_vault_password.key"
if os.path.isfile(keyfile):
    with open(keyfile, "r") as fp:
        key = fp.read()

    f = Fernet(key)

    redis = Redis(host="redis", port="6379")
    token = redis.get("ansible_vault_password")

    if token:
        print(f.decrypt(token).decode("utf-8"))
