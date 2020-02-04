#!/usr/bin/env bash
set -x

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

export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/ansible.cfg
if [[ -e $ENVIRONMENTS_DIRECTORY/$ENVIRONMENT/ansible.cfg ]]; then
    export ANSIBLE_CONFIG=$ENVIRONMENTS_DIRECTORY/$ENVIRONMENT/ansible.cfg
fi

cd $ENVIRONMENTS_DIRECTORY/$ENVIRONMENT

export IFS=","
for service in $services; do
  ansible-playbook \
    -e CONFIG_DIR=$ENVIRONMENTS_DIRECTORY/$ENVIRONMENT \
    -e @secrets.yml \
    -e @images.yml \
    -e @configuration.yml \
    -e kolla_action=$action \
    "$@" \
    $ANSIBLE_DIRECTORY/$ENVIRONMENT-$service.yml
done
