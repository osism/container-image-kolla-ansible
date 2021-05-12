#!/usr/bin/env bash

mkdir -p /interface/kolla-ansible
rsync -am --exclude='requirements*.yml' --include='*.yml' --exclude='*' /ansible/ /interface/kolla-ansible/
exec /usr/bin/dumb-init -- "$@"
