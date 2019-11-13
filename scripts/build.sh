#!/usr/bin/env bash
set -x

# Available environment variables
#
# BUILD_OPTS
# DOCKER_REGISTRY
# OPENSTACK_VERSION
# REPOSITORY
# VERSION

# Set default values

BUILD_OPTS=${BUILD_OPTS:-}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-rocky}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-index.docker.io}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
VERSION=${VERSION:-latest}

if [[ -n $TRAVIS_TAG ]]; then
    VERSION=${TRAVIS_TAG:1}
fi

HASH_REPOSITORY=$(git rev-parse --short HEAD)

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

TAG=$REPOSITORY:$OPENSTACK_VERSION-$VERSION

docker build \
    --build-arg "OPENSTACK_VERSION=$OPENSTACK_VERSION" \
    --build-arg "VERSION=$VERSION" \
    --label "io.osism.kolla-ansible=$HASH_REPOSITORY" \
    --squash \
    --no-cache \
    --tag "$TAG-$(git rev-parse --short HEAD)" \
    $BUID_OPTS .
