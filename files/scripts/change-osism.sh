#!/usr/bin/env bash

if [[ ! -e /usr/bin/git ]]; then
  apt-get update \
    && apt-get install --no-install-recommends -y git
fi

rm -rf /python-osism
git clone --depth 1 -b $1 https://github.com/osism/python-osism /python-osism

pushd /python-osism
pip3 uninstall -y osism
python3 -m pip --no-cache-dir install -U /python-osism
popd
