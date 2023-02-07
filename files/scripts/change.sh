#!/usr/bin/env bash

if [[ ! -e /usr/bin/git ]]; then
  apt-get update \
    && apt-get install --no-install-recommends -y git
fi

rm -rf /ansible/action_plugins/*
rm -rf /ansible/filter_plugins/*
rm -rf /ansible/library/*
rm -rf /ansible/module_utils/*
rm -rf /ansible/roles/*
rm -rf /repository

git clone https://github.com/openstack/kolla-ansible
git pull https://review.opendev.org/openstack/kolla-ansible $1

cp -r /repository/ansible/action_plugins/* /ansible/action_plugins
if [ -e /repository/ansible/filter_plugins ]; then
    cp -r /repository/ansible/filter_plugins/* /ansible/filter_plugins
fi
if [ -e /repository/ansible/module_utils ]; then
    cp -r /repository/ansible/module_utils/* /ansible/module_utils
fi

cp -r /repository/ansible/library/* /ansible/library
cp -r /repository/ansible/roles/* /ansible/roles

for playbook in $(find /repository/ansible -maxdepth 1 -name "*.yml" | grep -v nova.yml); do
    cp $playbook /ansible/kolla-"$(basename $playbook)"
done
