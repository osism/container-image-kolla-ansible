#!/usr/bin/env bash
set -x

# methods

function deploy() {
    service=$1
    shift
    echo "DEPLOY $service"
    docker exec -it test /run.sh deploy $service $@
}

# available environment variables
#
# DOCKER_REGISTRY
# OPENSTACK_VERSION
# REPOSITORY
# VERSION

# set default values

DOCKER_REGISTRY=${DOCKER_REGISTRY:-index.docker.io}
OPENSTACK_VERSION=${OPENSTACK_VERSION:-master}
REPOSITORY=${REPOSITORY:-osism/kolla-ansible}
VERSION=${VERSION:-latest}

if [[ -n $TRAVIS_TAG ]]; then
    VERSION=${TRAVIS_TAG:1}
fi

COMMIT=$(git rev-parse --short HEAD)

if [[ -n $DOCKER_REGISTRY ]]; then
    REPOSITORY="$DOCKER_REGISTRY/$REPOSITORY"
fi

if [[ $OPENSTACK_VERSION == "master" ]]; then
    tag=$REPOSITORY:latest
else
    tag=$REPOSITORY:$OPENSTACK_VERSION
fi

# run preparations

sudo apt-get update

if [[ $OPENSTACK_VERSION == "rocky" || $OPENSTACK_VERSION == "stein" ]]; then
    sudo apt-get install -y python python-docker python-pip
    sudo pip --no-cache-dir install \
      ansible \
      python-openstackclient \
      python-heatclient \
      python-magnumclient
else
    sudo apt-get install -y python3 python3-docker python3-pip python3-setuptools
    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
    sudo pip3 --no-cache-dir install \
      ansible \
      python-openstackclient \
      python-heatclient \
      python-magnumclient
fi

mkdir -p ~/.config/openstack
cp tests/environments/openstack/clouds.yml ~/.config/openstack/clouds.yml
cp tests/environments/openstack/secure.yml ~/.config/openstack/secure.yml

docker run --rm -v ${PWD}/tests:/workdir mikefarah/yq yq w --inplace /workdir/environments/kolla/configuration.yml openstack_release $OPENSTACK_VERSION

local_address=$(ip route get 8.8.8.8 | head -1 | cut -d ' ' -f 7)
docker run --rm -v ${PWD}/tests:/workdir mikefarah/yq yq w --inplace /workdir/inventory/host_vars/testnode.yml ansible_host $local_address

sudo modprobe dummy
sudo ip l a dummy_internal type dummy
sudo ip l a dummy_external type dummy
sudo ip a a 192.168.50.5/24 dev dummy_internal
sudo ip l s up dev dummy_internal
sudo ip l s up dev dummy_external

echo "192.168.50.200 api.osism.local api" | sudo tee -a /etc/hosts

free_device=$(sudo losetup -f)
sudo fallocate -l 5G /var/lib/cinder_data.img
sudo losetup $free_device /var/lib/cinder_data.img
sudo pvcreate $free_device
sudo vgcreate cinder-volumes $free_device

# start and prepare the kolla-ansible container

docker run --network=host --name test -d \
  -v /etc/hosts:/etc/hosts:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/tests:/opt/configuration:ro" \
  "$tag-$COMMIT" sleep infinity
docker cp tests/run.sh test:/run.sh

# prepare ssh

# ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ""
# cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
# docker cp $HOME/.ssh/id_rsa test:/ansible/secrets/id_rsa.operator

sudo service ssh start
cat tests/id_rsa.operator.pub >> ~/.ssh/authorized_keys

docker cp tests/id_rsa.operator test:/ansible/secrets/id_rsa.operator
docker exec -it test sudo chown dragon: /ansible/secrets/id_rsa.operator
docker exec -it test sudo chmod 0600 /ansible/secrets/id_rsa.operator

# get facts

docker exec -it test /run.sh _ facts

# infrastructure services

deploy common

deploy haproxy
echo "TEST haproxy"
sleep 15
ping -c 1 192.168.50.200

deploy elasticsearch
echo "TEST elasticsearch"
sleep 30
curl http://192.168.50.200:9200

# deploy kibana

deploy rabbitmq
echo "TEST rabbitmq"
sleep 15
docker exec -it rabbitmq rabbitmqctl cluster_status

deploy memcached
echo "TEST memcached"
sleep 5
echo stats | nc -q 1 192.168.50.5 11211

deploy redis
echo "TEST redis"
sleep 5
docker exec -it redis redis-cli -h 192.168.50.5 -a QHNA1SZRlOKzLADhUd5ZDgpHfQe6dNfr3bwEdY24 ping
docker exec -it redis redis-cli -h 192.168.50.5 -a QHNA1SZRlOKzLADhUd5ZDgpHfQe6dNfr3bwEdY24 info replication

deploy openvswitch
echo "TEST openvswitch"
sleep 5
docker exec -it openvswitch_vswitchd ovs-vsctl show

deploy etcd
echo "TEST etcd"
sleep 5
docker exec -it etcd etcdctl --endpoints http://192.168.50.5:2379 cluster-health

deploy mariadb
echo "TEST mariadb"
sleep 5
docker exec -it mariadb mysql -u root -pqNpdZmkKuUKBK3D5nZ08KMZ5MnYrGEe2hzH6XC0i -e "SHOW GLOBAL STATUS LIKE 'wsrep_%';"

# OpenStack services

deploy keystone
echo "TEST keystone"
sleep 5
openstack --os-cloud admin token issue

deploy horizon

deploy placement

deploy glance
echo "TEST glance"
sleep 5
openstack --os-cloud admin image list

deploy cinder
deploy iscsi
echo "TEST cinder"
sleep 5
openstack --os-cloud admin volume service list

deploy neutron
echo "TEST neutron"
sleep 5
openstack --os-cloud admin network agent list

# NOTE: RabbitMQ is skipped here. The RabbitMQ user/vhost is
#       already present and on Travis CI the tasks lead to an
#       error message.

deploy nova --skip-tags service-rabbitmq || exit 1
echo "TEST nova"
sleep 5
openstack --os-cloud admin compute service list

deploy barbican
echo "TEST barbican"

deploy heat
echo "TEST heat"
sleep 5
openstack --os-cloud admin orchestration service list

deploy magnum
echo "TEST magnum"
sleep 5
openstack --os-cloud admin coe service list
