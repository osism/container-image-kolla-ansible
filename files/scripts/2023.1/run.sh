#!/usr/bin/env bash

source /secrets.sh

ENVIRONMENT=${ENVIRONMENT:-kolla}
SUB=${SUB:-kolla}

if [[ $# -lt 2 ]]; then
    echo usage: osism-$ENVIRONMENT ACTION SERVICE [...]
    exit 1
fi

action=$1
shift

services=$1
shift

ANSIBLE_DIRECTORY=/ansible
CONFIGURATION_DIRECTORY=/opt/configuration
ENVIRONMENTS_DIRECTORY=$CONFIGURATION_DIRECTORY/environments
VAULT=${VAULT:-$ENVIRONMENTS_DIRECTORY/.vault_pass}

if [[ -e /ansible/ara.env ]]; then
    source /ansible/ara.env
fi

export ANSIBLE_STRATEGY_PLUGINS=/usr/share/ansible/plugins/mitogen/ansible_mitogen/plugins/strategy

# https://docs.openstack.org/kolla-ansible/latest/user/ansible-tuning.html#fact-variable-injection
export ANSIBLE_INJECT_FACT_VARS=False

export ANSIBLE_INVENTORY=$ANSIBLE_DIRECTORY/inventory/hosts.yml

export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/ansible.cfg
if [[ -e /inventory/ansible/ansible.cfg ]]; then
    export ANSIBLE_CONFIG=/inventory/ansible/ansible.cfg
elif [[ -e $ENVIRONMENTS_DIRECTORY/$SUB/ansible.cfg ]]; then
    export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/$SUB/ansible.cfg
fi

if [[ -w $ANSIBLE_INVENTORY ]]; then
    rsync -a /ansible/group_vars/ /ansible/inventory/group_vars/
    rsync -a /ansible/inventory.generics/ /ansible/inventory/
    rsync -a /opt/configuration/inventory/ /ansible/inventory/
    python3 /src/handle-inventory-overwrite.py
    cat /ansible/inventory/[0-9]* > /ansible/inventory/hosts
    rm /ansible/inventory/[0-9]*
fi

cd $ENVIRONMENTS_DIRECTORY/$SUB

export IFS=","
for service in $services; do
  if [[ ! -e $ANSIBLE_DIRECTORY/$ENVIRONMENT-$service.yml ]]; then
    echo "warning: playbook for service $service does not exist"
  else
    ansible-playbook \
      --vault-password-file $VAULT \
      -e CONFIG_DIR=$ENVIRONMENTS_DIRECTORY/$SUB \
      -e @$ENVIRONMENTS_DIRECTORY/configuration.yml \
      -e @$ENVIRONMENTS_DIRECTORY/secrets.yml \
      -e @secrets.yml \
      -e @images.yml \
      -e @configuration.yml \
      -e kolla_action=$action \
      "$@" \
      $ANSIBLE_DIRECTORY/$ENVIRONMENT-$service.yml
  fi
done
