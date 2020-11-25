#!/usr/bin/env bash
set -x

# Available environment variables
#
# DOCKER_REGISTRY
# OPENSTACK_VERSION
# REPOSITORY
# VERSION

# Set default values

DOCKER_REGISTRY=${DOCKER_REGISTRY:-quay.io}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-master}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
VERSION=${VERSION:-latest}

COMMIT=$(git rev-parse --short HEAD)

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

if [[ $OPENSTACK_VERSION == "master" ]]; then
    tag=$REPOSITORY:latest

    docker tag "$tag-$COMMIT" "$tag"
    docker push "$tag"
else
    tag=$REPOSITORY:$OPENSTACK_VERSION

    docker tag "$tag-$COMMIT" "$tag-$VERSION"
    docker push "$tag-$VERSION"

    docker tag "$tag-$COMMIT" "$tag"
    docker push "$tag"
fi
