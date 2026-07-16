#!/bin/bash
# Ponto de entrada do container: sobe o Open vSwitch (ovsdb-server +
# ovs-vswitchd) em modo userspace antes de liberar o shell/comando
# pedido pelo usuário. Sem systemd dentro do container, isso precisa
# ser feito manualmente a cada "docker run"/"docker compose up".
set -e

mkdir -p /var/run/openvswitch /var/log/openvswitch /etc/openvswitch

if [ ! -f /etc/openvswitch/conf.db ]; then
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
fi

ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --private-key=db:Open_vSwitch,SSL,private_key \
    --certificate=db:Open_vSwitch,SSL,certificate \
    --bootstrap-ca-cert=db:Open_vSwitch,SSL,ca_cert \
    --pidfile --detach --log-file=/var/log/openvswitch/ovsdb-server.log

ovs-vsctl --no-wait init

# datapath_type=netdev = datapath em userspace (não usa openvswitch.ko).
# É o que permite o OVS funcionar dentro da VM Linux do Docker Desktop.
ovs-vswitchd --pidfile --detach --log-file=/var/log/openvswitch/ovs-vswitchd.log

echo "*** Open vSwitch ativo (datapath userspace) dentro do container."
mkdir -p /app/resultados

exec "$@"
