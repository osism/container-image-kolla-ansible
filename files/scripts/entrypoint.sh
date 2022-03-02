#!/usr/bin/env bash

mkdir -p /interface/kolla-ansible /interface/versions /interface/overlays

rsync -am --exclude='requirements*.yml' --include='*.yml' --exclude='*' /ansible/ /interface/kolla-ansible/
cp /ansible/group_vars/all/versions.yml /interface/versions/kolla-ansible.yml
cp /overlays/kolla-ansible.yml /interface/overlays/kolla-ansible.yml

exec /usr/bin/dumb-init -- "$@"
