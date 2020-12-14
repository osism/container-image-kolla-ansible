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
CREATED=$(date --rfc-3339=ns)
DOCKER_REGISTRY=${DOCKER_REGISTRY:-quay.io}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-master}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
REVISION=$(git rev-parse --short HEAD)
VERSION=${VERSION:-latest}

. defaults/$OPENSTACK_VERSION.sh

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

if [[ $OPENSTACK_VERSION == "master" ]]; then
    tag=$REPOSITORY:latest
else
    tag=$REPOSITORY:$OPENSTACK_VERSION
fi

docker buildx build \
    --build-arg "OPENSTACK_VERSION=$OPENSTACK_VERSION" \
    --build-arg "UBUNTU_VERSION=$UBUNTU_VERSION" \
    --build-arg "VERSION=$VERSION" \
    --label "org.opencontainers.image.created=$CREATED" \
    --label "org.opencontainers.image.documentation=https://docs.osism.de" \
    --label "org.opencontainers.image.licenses=ASL 2.0" \
    --label "org.opencontainers.image.revision=$REVISION" \
    --label "org.opencontainers.image.source=https://github.com/osism/docker-image-kolla-ansible" \
    --label "org.opencontainers.image.title=kolla-ansible" \
    --label "org.opencontainers.image.url=https://www.osism.de" \
    --label "org.opencontainers.image.vendor=Betacloud Solutions GmbH" \
    --label "org.opencontainers.image.version=$VERSION" \
    --tag "$tag-$(git rev-parse --short HEAD)" \
    $BUID_OPTS .
