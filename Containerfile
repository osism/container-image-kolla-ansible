ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm as builder

ARG OPENSTACK_VERSION
ARG VERSION

ARG USER_ID=45000
ARG GROUP_ID=45000
ARG GROUP_ID_DOCKER=999

ENV DEBIAN_FRONTEND noninteractive

USER root

COPY --link overlays /overlays
COPY --link patches /patches

COPY --link files/library /ansible/library
COPY --link files/tasks /ansible/tasks

COPY --link files/playbooks/kolla-*.yml /ansible/
COPY --link files/refresh-containers.yml /refresh-containers.yml

COPY --link files/scripts/change.sh /change.sh
COPY --link files/scripts/remove-common-as-dependency.py /remove-common-as-dependency.py
COPY --link files/scripts/split-kolla-ansible-site.py /split-kolla-ansible-site.py
COPY --link files/scripts/$OPENSTACK_VERSION/run.sh /run.sh
COPY --link files/scripts/secrets.sh /secrets.sh
COPY --link files/scripts/entrypoint.sh /entrypoint.sh
COPY --link files/scripts/ansible-vault.py /ansible-vault.py

COPY --link files/ansible.cfg /etc/ansible/ansible.cfg
COPY --link files/ara.env /ansible/ara.env
COPY --link files/requirements.yml /ansible/galaxy/requirements.yml

COPY --link files/src /src

ADD https://github.com/mitogen-hq/mitogen/archive/refs/tags/v0.3.7.tar.gz /mitogen.tar.gz

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3003
RUN <<EOF
set -e
set -x

# show motd
echo '[ ! -z "$TERM" -a -r /etc/motd ] && cat /etc/motd' >> /etc/bash.bashrc

# upgrade/install required packages
apt-get update
apt-get install -y --no-install-recommends \
  build-essential \
  dumb-init \
  git \
  gnupg-agent \
  jq \
  libffi-dev \
  libssh-dev \
  libssl-dev \
  libyaml-dev \
  openssh-client \
  patch \
  procps \
  python3-dev \
  python3-pip \
  python3-setuptools \
  python3-wheel \
  rsync \
  sshpass

python3 -m pip install --no-cache-dir --upgrade 'pip==24.0'
pip3 install --no-cache-dir -r /src/requirements.txt

update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# add user
groupadd -g "$GROUP_ID" dragon
groupadd -g "$GROUP_ID_DOCKER" docker
useradd -l -g dragon -G docker -u "$USER_ID" -m -d /ansible dragon

# prepare release repository
git clone https://github.com/osism/release /release

# prepare project repository
git clone https://github.com/osism/ansible-playbooks /playbooks
( cd /playbooks || exit; git fetch --all --force; git checkout "$(yq -M -r .playbooks_version "/release/$VERSION/openstack.yml")" )

git clone https://github.com/osism/defaults /defaults
( cd /defaults || exit; git fetch --all --force; git checkout "$(yq -M -r .defaults_version "/release/$VERSION/openstack.yml")" )

git clone https://github.com/osism/cfg-generics /generics
( cd /generics || exit; git fetch --all --force; git checkout "$(yq -M -r .generics_version "/release/$VERSION/openstack.yml")" )

git clone https://github.com/osism/kolla-operations /operations
( cd /operations || exit; git fetch --all --force; git checkout "$(yq -M -r .operations_version "/release/$VERSION/base.yml")" )

# add inventory files
mkdir -p /ansible/inventory.generics /ansible/inventory
cp /generics/inventory/50-ceph /ansible/inventory.generics/50-ceph
cp /generics/inventory/51-ceph /ansible/inventory.generics/51-ceph
cp /generics/inventory/50-kolla /ansible/inventory.generics/50-kolla
cp /generics/inventory/51-kolla /ansible/inventory.generics/51-kolla

# run preparations
mkdir -p /ansible/galaxy /ansible/group_vars/all
python3 /src/render-python-requirements.py
python3 /src/render-versions.py

# install required python packages
pip3 install --no-cache-dir -r /requirements.txt

# set ansible version in the motd
ansible_version=$(python3 -c 'import ansible; print(ansible.release.__version__)')
sed -i -e "s/ANSIBLE_VERSION/$ansible_version/" /etc/motd

# create required directories
mkdir -p \
  /ansible \
  /ansible/action_plugins \
  /ansible/cache \
  /ansible/filter_plugins \
  /ansible/library \
  /ansible/logs \
  /ansible/module_utils \
  /ansible/roles \
  /ansible/secrets \
  /ansible/tasks \
  /interface \
  /share

# install required ansible collections & roles
ansible-galaxy role install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/roles
ln -s /usr/share/ansible/roles /ansible/galaxy

ansible-galaxy collection install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/collections
ln -s /usr/share/ansible/collections /ansible/collections

# prepare project repository
if [ "$OPENSTACK_VERSION" = "master" ]; then git clone https://opendev.org/openstack/kolla-ansible /repository; fi
if [ "$OPENSTACK_VERSION" != "master" ]; then git clone -b stable/$OPENSTACK_VERSION https://opendev.org/openstack/kolla-ansible /repository; fi

# apply patches
for patchfile in $(find /patches/$OPENSTACK_VERSION -name "*.patch"); do
  echo $patchfile;
  ( cd /repository && patch --forward --batch -p1 --dry-run ) < $patchfile || exit 1
  ( cd /repository && patch --forward --batch -p1 ) < $patchfile
done

# install mitogen ansible plugin
mkdir -p /usr/share/mitogen
tar xzf /mitogen.tar.gz --strip-components=1 -C /usr/share/mitogen
rm -rf /usr/share/mitogen/{tests,docs,.ci,.lgtm.yml,.travis.yml}
rm /mitogen.tar.gz

# project specific instructions
ln -s /ansible/kolla-gather-facts.yml /ansible/gather-facts.yml
pip3 install --no-cache-dir -r /repository/requirements.txt
pip3 install --no-cache-dir /repository
mkdir -p /ansible/group_vars
cp -r /defaults/* /ansible/group_vars/
rm -f /ansible/group_vars/LICENSE /ansible/group_vars/README.md
python3 /remove-common-as-dependency.py
python3 /split-kolla-ansible-site.py
cp -r /repository/ansible/action_plugins/* /ansible/action_plugins
if [ -e /repository/ansible/filter_plugins ]; then cp -r /repository/ansible/filter_plugins/* /ansible/filter_plugins; fi
if [ -e /repository/ansible/module_utils ]; then cp -r /repository/ansible/module_utils/* /ansible/module_utils; fi
cp /repository/ansible/library/* /ansible/library
cp -r /repository/ansible/roles/* /ansible/roles
for playbook in $(find /repository/ansible -maxdepth 1 -name "*.yml" | grep -v nova.yml); do echo $playbook && cp $playbook /ansible/kolla-"$(basename $playbook)"; done
cp /repository/ansible/nova.yml /ansible/kolla-nova.yml
rm -f /ansible/kolla-kolla-host.yml /ansible/kolla-post-deploy.yml
rm /remove-common-as-dependency.py
rm /split-kolla-ansible-site.py
mkdir /ansible/files
cp /repository/tools/cleanup-* /ansible/files

# add refresh-containers action
find /ansible/roles/ -name config.yml -print0 | xargs -0 -I{} dirname {} | xargs -I{} cp /refresh-containers.yml {}/refresh-containers.yml
rm /refresh-containers.yml

# prepare overlays
mv /overlays/$OPENSTACK_VERSION/kolla-ansible.yml /overlays
if [ -e /overlays/release/$VERSION ]; then mv /overlays/release/$VERSION/release-kolla-ansible.yml /overlays; fi
for d in $(find /overlays -mindepth 1 -type d); do rm -rf $d; done

# copy ara configuration
python3 -m ara.setup.env >> /ansible/ara.env

# set correct permssions
chown -R dragon: /ansible /share /interface

# cleanup
apt-get clean
apt-get remove -y \
  build-essential \
  git \
  libffi-dev \
  libssh-dev \
  libssl-dev \
  libyaml-dev \
  python3-dev
apt-get autoremove -y

rm -rf \
  /patches \
  /release \
  /root/.cache \
  /tmp/* \
  /usr/share/doc/* \
  /usr/share/man/* \
  /var/lib/apt/lists/* \
  /var/tmp/*

pip3 install --no-cache-dir pyclean==3.0.0
pyclean /usr
pip3 uninstall -y pyclean
EOF

COPY --link files/playbooks/$OPENSTACK_VERSION/kolla-*.yml /ansible/
# prepare list of playbooks
RUN python3 /src/render-playbooks.py

USER dragon

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm

COPY --link --from=builder / /

VOLUME ["/ansible/cache", "/ansible/logs", "/ansible/secrets", "/share", "/interface"]
USER dragon
WORKDIR /ansible
ENTRYPOINT ["/entrypoint.sh"]
