#!/usr/bin/env python3

# NOTE: This is a first step to make Ansible Vault usable via OSISM workers.
#       It's not ready in that form yet.

from redis import Redis

redis = Redis(host="redis", port="6379")
ansible_vault_password = redis.get("ansible_vault_password")

if ansible_vault_password:
    print(ansible_vault_password)
