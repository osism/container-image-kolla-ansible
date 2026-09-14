#!/usr/bin/env bash

# source: https://github.com/docker-library/mariadb/blob/master/docker-entrypoint.sh
#
# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for Docker's secrets feature)
file_env() {
        local var="$1"
        local fileVar="${var}_FILE"
        local def="${2:-}"
        if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
                echo "Both $var and $fileVar are set (but are exclusive)"
                exit 1
        fi
        local val="$def"
        if [ "${!var:-}" ]; then
                val="${!var}"
        elif [ "${!fileVar:-}" ]; then
                val="$(< "${!fileVar}")"
        fi
        export "$var"="$val"
        unset "$fileVar"
}

NETBOX_TOKEN_FILE=${NETBOX_TOKEN_FILE:-/run/secrets/NETBOX_TOKEN}

if [[ -e $NETBOX_TOKEN_FILE ]]; then
    file_env 'NETBOX_TOKEN'
fi

# The vault password reaches a run script either through VAULT -- set by the
# OSISM worker to the redis-backed helper, or by an operator pointing at a file
# of their own -- or through the default it falls back to,
# $ENVIRONMENTS_DIRECTORY/.vault_pass. Neither is guaranteed to exist: the
# configuration template stopped shipping that file, and the worker leaves
# VAULT unset whenever redis holds no password, which is the state after every
# manager container recreate. Since ansible-playbook is always invoked with
# --vault-password-file, an absent file aborts the play with the resolved path
# reported as missing, which sends the operator looking for a file in the
# configuration repository rather than at the password itself. Name the state
# and both remedies instead. Do not prompt: the worker runs these scripts
# without a TTY, so an interactive fallback would block rather than help.
#
# Call this after the script has changed into the environment directory, not
# where VAULT is resolved: an operator-supplied VAULT may be a relative path,
# and ansible resolves it from the directory it is invoked in.
require_vault_password() {
    if [[ ! -e $VAULT ]]; then
        echo "ERROR: No Ansible Vault password is available ($VAULT does not exist)."
        echo "Run 'osism set vault password' on the manager, or add"
        echo "environments/.vault_pass to the configuration repository for"
        echo "unattended operation."
        exit 1
    fi
}
