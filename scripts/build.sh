#!/usr/bin/env bash
set -x

# Available environment variables
#
# BUILD_OPTS
# DOCKER_REGISTRY
# IS_RELEASE
# OPENSTACK_VERSION
# REPOSITORY
# VERSION

# Set default values

BUILD_OPTS=${BUILD_OPTS:-}
CREATED=$(date --rfc-3339=ns)
DOCKER_REGISTRY=${DOCKER_REGISTRY:-quay.io}
IS_RELEASE=${IS_RELEASE:-false}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-master}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
REVISION=$(git rev-parse --short HEAD)
VERSION=${VERSION:-latest}

# NOTE: For builds for a specific release, the OpenStack version is taken from the release repository.
if [[ $VERSION != "latest" ]]; then
    filename=$(curl -L https://raw.githubusercontent.com/osism/release/master/$VERSION/openstack.yml)
    OPENSTACK_VERSION=$(curl -L https://raw.githubusercontent.com/osism/release/master/$VERSION/$filename | grep "openstack_version:" | awk -F': ' '{ print $2 }')
fi

. defaults/$OPENSTACK_VERSION.sh

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

buildah build-using-dockerfile \
    --squash \
    --format docker \
    --build-arg "IS_RELEASE=$IS_RELEASE" \
    --build-arg "OPENSTACK_VERSION=$OPENSTACK_VERSION" \
    --build-arg "VERSION=$VERSION" \
    --label "org.opencontainers.image.created=$CREATED" \
    --label "org.opencontainers.image.documentation=https://docs.osism.tech" \
    --label "org.opencontainers.image.licenses=ASL 2.0" \
    --label "org.opencontainers.image.revision=$REVISION" \
    --label "org.opencontainers.image.source=https://github.com/osism/docker-image-kolla-ansible" \
    --label "org.opencontainers.image.title=kolla-ansible" \
    --label "org.opencontainers.image.url=https://www.osism.tech" \
    --label "org.opencontainers.image.vendor=OSISM GmbH" \
    --label "org.opencontainers.image.version=$VERSION" \
    --label "de.osism.release.openstack=$OPENSTACK_VERSION" \
    --tag "$(git rev-parse --short HEAD)" \
    $BUID_OPTS .

buildah push $(git rev-parse --short HEAD) docker-daemon:kolla-ansible:$(git rev-parse --short HEAD)
