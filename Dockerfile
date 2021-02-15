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

COPY files/inventory /ansible/inventory
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

COPY files/scripts/generate-images-file.py /generate-images-file.py
COPY files/scripts/remove-common-as-dependency.py /remove-common-as-dependency.py
COPY files/scripts/split-kolla-ansible-site.py /split-kolla-ansible-site.py
COPY files/scripts/$OPENSTACK_VERSION/run.sh /run.sh
COPY files/scripts/secrets.sh /secrets.sh

COPY files/ansible.cfg /etc/ansible/ansible.cfg
COPY files/defaults.yml /ansible/group_vars/all/defaults.yml
COPY files/images.yml /ansible/group_vars/all/images.yml
COPY files/requirements.yml /ansible/galaxy/requirements.yml
COPY files/refresh-containers.yml /tmp/refresh-containers.yml

COPY files/dragon_sudoers /etc/sudoers.d/dragon_sudoers

COPY files/src /src

# add inventory files

ADD https://raw.githubusercontent.com/osism/cfg-generics/master/inventory/50-ceph /ansible/inventory/50-ceph
ADD https://raw.githubusercontent.com/osism/cfg-generics/master/inventory/51-ceph /ansible/inventory/51-ceph

ADD https://raw.githubusercontent.com/osism/cfg-generics/master/inventory/50-kolla /ansible/inventory/50-kolla
ADD https://raw.githubusercontent.com/osism/cfg-generics/master/inventory/51-kolla /ansible/inventory/51-kolla

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
        sudo \
        vim-tiny \
    && python3 -m pip install --upgrade pip \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && rm -rf /var/lib/apt/lists/*

# add user

RUN chmod 0440 /etc/sudoers.d/dragon_sudoers \
    && groupadd -g $GROUP_ID dragon \
    && groupadd -g $GROUP_ID_DOCKER docker \
    && useradd -g dragon -G docker -u $USER_ID -m -d /ansible dragon

# # run preparations

WORKDIR /src
RUN git clone https://github.com/osism/release /release \
    && pip3 install --no-cache-dir -r requirements.txt \
    && mkdir -p /ansible/galaxy /ansible/group_vars/all \
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

# exportes as volumes
RUN mkdir -p \
        /ansible/cache \
        /ansible/logs \
        /ansible/secrets \
        /share

# install required ansible collections & roles

RUN ansible-galaxy role install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/roles \
    && ln -s /usr/share/ansible/roles /ansible/galaxy \
    && ansible-galaxy collection install -v -f -r /ansible/galaxy/requirements.yml -p /usr/share/ansible/collections \
    && ln -s /usr/share/ansible/collections /ansible/collections

# prepare project repository

RUN if [ $OPENSTACK_VERSION = "master" ]; then git clone https://github.com/openstack/kolla-ansible /repository; fi \
    && if [ $OPENSTACK_VERSION != "master" ]; then git clone -b stable/$OPENSTACK_VERSION https://github.com/openstack/kolla-ansible /repository; fi

RUN for patchfile in $(find /patches/$OPENSTACK_VERSION -name "*.patch"); do \
        echo $patchfile; \
        ( cd /repository && patch --forward --batch -p1 --dry-run ) < $patchfile || exit 1; \
        ( cd /repository && patch --forward --batch -p1 ) < $patchfile; \
       done \
    && rsync -avz /overlays/ /repository/

# project specific instructions

RUN cp /repository/ansible/group_vars/all.yml /ansible/group_vars/all/defaults-kolla.yml \
    && ln -s /ansible/kolla-gather-facts.yml /ansible/gather-facts.yml \
    && pip3 install --no-cache-dir -r /repository/requirements.txt \
    && pip3 install --no-cache-dir /repository \
    && python3 /generate-images-file.py > /ansible/group_vars/all/images-project.yml \
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
    && rm /generate-images-file.py \
    && rm /remove-common-as-dependency.py \
    && rm /split-kolla-ansible-site.py \
    && mkdir /ansible/files \
    && cp /repository/tools/cleanup-* /ansible/files \
    && find /ansible/roles/ -name config.yml -print0 | xargs -0 -I{} dirname {} | xargs -I{} cp /tmp/refresh-containers.yml {}/refresh-containers.yml \
    && rm /tmp/refresh-containers.yml

RUN python3 -m ara.setup.env > /ansible/ara.env

# set correct permssions

RUN chown -R dragon: /ansible /share

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
      /src \
      /tmp/* \
      /usr/share/doc/* \
      /usr/share/man/* \
      /var/tmp/*

VOLUME ["/ansible/cache", "/ansible/logs", "/ansible/secrets", "/share"]

USER dragon
WORKDIR /ansible

ENTRYPOINT ["/usr/bin/dumb-init", "--"]

LABEL "org.opencontainers.image.documentation"="https://docs.osism.de" \
      "org.opencontainers.image.licenses"="ASL 2.0" \
      "org.opencontainers.image.source"="https://github.com/osism/docker-image-kolla-ansible" \
      "org.opencontainers.image.url"="https://www.osism.de" \
      "org.opencontainers.image.vendor"="Betacloud Solutions GmbH"
