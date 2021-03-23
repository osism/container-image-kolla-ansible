#!/usr/bin/env bash

source /secrets.sh

ENVIRONMENT=kolla

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

if [[ -e /ansible/ara.env ]]; then
    source /ansible/ara.env
fi

if [[ ! -e /run/secrets/NETBOX_TOKEN ]]; then
    rm -f /ansible/inventory/99-netbox.yml
fi

export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/ansible.cfg
if [[ -e $ENVIRONMENTS_DIRECTORY/$ENVIRONMENT/ansible.cfg ]]; then
    export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/$ENVIRONMENT/ansible.cfg
fi

export ANSIBLE_INVENTORY=$ANSIBLE_DIRECTORY/inventory
rsync -a /ansible/group_vars/ /ansible/inventory/group_vars/
rsync -a /opt/configuration/inventory/ /ansible/inventory/
python3 /src/handle-inventory-overwrite.py
cat /ansible/inventory/[0-9]* > /ansilble/inventory/hosts
rm /ansible/inventory/[0-9]*

cd $ENVIRONMENTS_DIRECTORY/$ENVIRONMENT

export IFS=","
for service in $services; do
  if [[ ! -e $ANSIBLE_DIRECTORY/$ENVIRONMENT-$service.yml ]]; then
    echo "warning: playbook for service $service does not exist"
  else
    ansible-playbook \
      --vault-password-file $ENVIRONMENTS_DIRECTORY/.vault_pass \
      -e CONFIG_DIR=$ENVIRONMENTS_DIRECTORY/$ENVIRONMENT \
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
