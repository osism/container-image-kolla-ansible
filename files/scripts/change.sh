#!/usr/bin/env bash

if [[ ! -e /usr/bin/git ]]; then
  apt-get update \
    && apt-get install --no-install-recommends -y git
fi

if [[ "$1" == "kolla-ansible" ]]; then

    rm -rf /ansible/action_plugins/*
    rm -rf /ansible/filter_plugins/*
    rm -rf /ansible/library/*
    rm -rf /ansible/module_utils/*
    rm -rf /ansible/roles/*
    rm -rf /repository

    git clone https://opendev.org/openstack/kolla-ansible /repository
    git -C /repository config advice.detachedHead false
    git -C /repository fetch https://review.opendev.org/openstack/kolla-ansible.git $2
    git -C /repository checkout FETCH_HEAD


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
elif [[ "$1" == "osism" ]]; then
    rm -rf /python-osism
    git clone --depth 1 -b $2 https://github.com/osism/python-osism /python-osism

    pushd /python-osism
    pip3 uninstall -y osism
    python3 -m pip --no-cache-dir install -U /python-osism
    popd
elif [[ "$1" == "operations" ]]; then
    rm -rf /operations
    git clone --depth 1 -b $2 https://github.com/osism/kolla-operations /operations
fi
