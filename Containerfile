ARG UBUNTU_VERSION=20.04
FROM ubuntu:${UBUNTU_VERSION}

ARG VERSION
ARG OPENSTACK_VERSION

ARG USER_ID=45000
ARG GROUP_ID=45000
ARG GROUP_ID_DOCKER=999

ENV DEBIAN_FRONTEND noninteractive

USER root

COPY overlays/$OPENSTACK_VERSION /overlays
COPY patches /patches

COPY files/library /ansible/library
COPY files/plugins /ansible/plugins
COPY files/tasks /ansible/tasks

COPY files/playbooks/$OPENSTACK_VERSION/kolla-common.yml /ansible/kolla-common.yml
COPY files/playbooks/kolla-bifrost-keypair.yml /ansible/kolla-bifrost-keypair.yml
COPY files/playbooks/kolla-facts.yml /ansible/kolla-facts.yml
COPY files/playbooks/kolla-mariadb-dynamic-rows.yml /ansible/kolla-mariadb-dynamic-rows.yml
COPY files/playbooks/kolla-nova-compute.yml /ansible/kolla-nova-compute.yml
COPY files/playbooks/kolla-purge.yml /ansible/kolla-purge.yml
COPY files/playbooks/kolla-rgw-endpoint.yml /ansible/kolla-rgw-endpoint.yml
COPY files/playbooks/kolla-testbed.yml /ansible/kolla-testbed.yml
COPY files/playbooks/kolla-testbed-identity.yml /ansible/kolla-testbed-identity.yml

COPY files/scripts/remove-common-as-dependency.py /remove-common-as-dependency.py
COPY files/scripts/split-kolla-ansible-site.py /split-kolla-ansible-site.py
COPY files/scripts/$OPENSTACK_VERSION/run.sh /run.sh
COPY files/scripts/secrets.sh /secrets.sh
COPY files/scripts/entrypoint.sh /entrypoint.sh

COPY files/ansible.cfg /etc/ansible/ansible.cfg
COPY files/requirements.yml /ansible/galaxy/requirements.yml
COPY files/refresh-containers.yml /tmp/refresh-containers.yml

COPY files/src /src

# fix hadolint DL4006
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# show motd
RUN echo '[ ! -z "$TERM" -a -r /etc/motd ] && cat /etc/motd' >> /etc/bash.bashrc

# upgrade/install required packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        dumb-init \
        git \
        gnupg-agent \
        jq \
        libffi-dev \
        libssl-dev \
        libyaml-dev \
        openssh-client \
        patch \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-wheel \
        rsync \
        sshpass \
        vim-tiny \
    && python3 -m pip install --no-cache-dir --upgrade pip==21.1.3 \
    && pip3 install --no-cache-dir -r /src/requirements.txt \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && rm -rf /var/lib/apt/lists/*

# add user
RUN groupadd -g $GROUP_ID dragon \
    && groupadd -g $GROUP_ID_DOCKER docker \
    && useradd -l -g dragon -G docker -u $USER_ID -m -d /ansible dragon

# prepare release repository
RUN git clone https://github.com/osism/release /release

# prepare python-osism repository
# hadolint ignore=DL3013
RUN git clone https://github.com/osism/python-osism /python-osism \
    && pip3 install /python-osism

# prepare project repository

# hadolint ignore=DL3003
RUN git clone https://github.com/osism/ansible-playbooks /playbooks \
    && ( cd /playbooks || exit; git fetch --all --force; git checkout "$(yq -M -r .playbooks_version "/release/$VERSION/base.yml")" )

# hadolint ignore=DL3003
RUN git clone https://github.com/osism/ansible-defaults /defaults \
    && ( cd /defaults || exit; git fetch --all --force; git checkout "$(yq -M -r .defaults_version "/release/$VERSION/base.yml")" )

# hadolint ignore=DL3003
RUN git clone https://github.com/osism/cfg-generics /generics  \
    && ( cd /generics || exit; git fetch --all --force; git checkout "$(yq -M -r .generics_version "/release/$VERSION/base.yml")" )

# hadolint ignore=DL3003
RUN git clone https://github.com/osism/kolla-operations /operations \
    && ( cd /operations || exit; git fetch --all --force; git checkout "$(yq -M -r .operations_version "/release/$VERSION/base.yml")" )

# add inventory files
RUN mkdir -p /ansible/inventory.generics /ansible/inventory \
    && cp /generics/inventory/50-ceph /ansible/inventory.generics/50-ceph \
    && cp /generics/inventory/51-ceph /ansible/inventory.generics/51-ceph \
    && cp /generics/inventory/50-kolla /ansible/inventory.generics/50-kolla \
    && cp /generics/inventory/51-kolla /ansible/inventory.generics/51-kolla

# run preparations
WORKDIR /src
RUN mkdir -p /ansible/galaxy /ansible/group_vars/all \
    && python3 /src/render-python-requirements.py \
    && python3 /src/render-versions.py

WORKDIR /

# install required python packages
RUN pip3 install --no-cache-dir -r /requirements.txt

# set ansible version in the motd
RUN ansible_version=$(python3 -c 'import ansible; print(ansible.release.__version__)') \
    && sed -i -e "s/ANSIBLE_VERSION/$ansible_version/" /etc/motd

# create required directories

# internal use only
RUN mkdir -p \
        /ansible \
        /ansible/action_plugins \
        /ansible/filter_plugins \
        /ansible/library \
        /ansible/roles \
        /ansible/tasks

# volumes
# hadolint ignore=DL3059
RUN mkdir -p \
        /ansible/cache \
        /ansible/logs \
        /ansible/secrets \
        /share \
        /interface

# install required ansible collections & roles
RUN ansible-galaxy role install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/roles \
    && ln -s /usr/share/ansible/roles /ansible/galaxy \
    && ansible-galaxy collection install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/collections \
    && ln -s /usr/share/ansible/collections /ansible/collections

# prepare project repository
RUN if [ $OPENSTACK_VERSION = "master" ]; then git clone https://github.com/openstack/kolla-ansible /repository; fi \
    && if [ $OPENSTACK_VERSION != "master" ]; then git clone -b stable/$OPENSTACK_VERSION https://github.com/openstack/kolla-ansible /repository; fi

# hadolint ignore=DL3059
RUN for patchfile in $(find /patches/$OPENSTACK_VERSION -name "*.patch"); do \
        echo $patchfile; \
        ( cd /repository && patch --forward --batch -p1 --dry-run ) < $patchfile || exit 1; \
        ( cd /repository && patch --forward --batch -p1 ) < $patchfile; \
       done \
    && rsync -avz /overlays/ /repository/

# project specific instructions
RUN ln -s /ansible/kolla-gather-facts.yml /ansible/gather-facts.yml \
    && pip3 install --no-cache-dir -r /repository/requirements.txt \
    && pip3 install --no-cache-dir /repository \
    && mkdir -p /ansible/group_vars \
    && cp -r /defaults/* /ansible/group_vars/ \
    && rm -f /ansible/group_vars/LICENSE /ansible/group_vars/README.md \
    && python3 /remove-common-as-dependency.py \
    && python3 /split-kolla-ansible-site.py \
    && cp -r /repository/ansible/action_plugins/* /ansible/action_plugins \
    && if [ -e /repository/ansible/filter_plugins ]; then cp -r /repository/ansible/filter_plugins/* /ansible/filter_plugins; fi \
    && cp /repository/ansible/library/* /ansible/library \
    && cp -r /repository/ansible/roles/* /ansible/roles \
    && for playbook in $(find /repository/ansible -maxdepth 1 -name "*.yml" | grep -v nova.yml); do echo $playbook && cp $playbook /ansible/kolla-"$(basename $playbook)"; done \
    && if [ $OPENSTACK_VERSION != "rocky" ] && [ $OPENSTACK_VERSION != "stein" ]; then cp /repository/ansible/nova.yml /ansible/kolla-nova.yml; fi \
    && if [ $OPENSTACK_VERSION == "rocky" ]; then mkdir /ansible/roles/placement; fi \
    && rm -f /ansible/kolla-kolla-host.yml /ansible/kolla-post-deploy.yml \
    && rm /remove-common-as-dependency.py \
    && rm /split-kolla-ansible-site.py \
    && mkdir /ansible/files \
    && cp /repository/tools/cleanup-* /ansible/files \
    && find /ansible/roles/ -name config.yml -print0 | xargs -0 -I{} dirname {} | xargs -I{} cp /tmp/refresh-containers.yml {}/refresh-containers.yml \
    && rm /tmp/refresh-containers.yml

# copy ara configuration
RUN python3 -m ara.setup.env > /ansible/ara.env

# set correct permssions
RUN chown -R dragon: /ansible /share /interface

# cleanup
RUN apt-get clean \
    && apt-get remove -y  \
      build-essential \
      git \
      libffi-dev \
      libssl-dev \
      libyaml-dev \
      python3-dev \
    && apt-get autoremove -y \
    && rm -rf \
      /overlays \
      /patches \
      /release \
      /root/.cache \
      /tmp/* \
      /usr/share/doc/* \
      /usr/share/man/* \
      /var/tmp/*

VOLUME ["/ansible/cache", "/ansible/logs", "/ansible/secrets", "/share", "/interface"]

USER dragon
WORKDIR /ansible

ENTRYPOINT ["/entrypoint.sh"]
