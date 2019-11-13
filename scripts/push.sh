#!/usr/bin/env bash
set -x

# Available environment variables
#
# DOCKER_REGISTRY
# OPENSTACK_VERSION
# PUSH_COMMIT
# REPOSITORY
# VERSION

# Set default values

DOCKER_REGISTRY=${DOCKER_REGISTRY:-index.docker.io}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-rocky}
PUSH_COMMIT=${PUSH_COMMIT:-false}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
VERSION=${VERSION:-latest}

if [[ -n $TRAVIS_TAG ]]; then
    VERSION=${TRAVIS_TAG:1}
fi

COMMIT=$(git rev-parse --short HEAD)

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

if [[ $PUSH_COMMIT == "true" ]]; then
    docker push "$REPOSITORY:$VERSION-$COMMIT"
fi

docker tag "$REPOSITORY:$OPENSTACK_VERSION-$VERSION-$COMMIT" "$REPOSITORY:$OPENSTACK_VERSION-$VERSION"
docker push "$REPOSITORY:$OPENSTACK_VERSION-$VERSION"
