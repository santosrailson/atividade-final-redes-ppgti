import os
import sys
import argparse

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from p4_mininet import P4Switch, P4Host

CAMINHO_COMUTADOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'p4', 'comutador.p4')
CAMINHO_TABELAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'p4', 'tabelas')

class TopologiaTransporte5G(Topo):
    def __init__(self, **params):
        Topo.__init__(self, **params)

        argumentos_comutador = {
            'sw_path': getattr(TopologiaTransporte5G, 'caminho_comportamento', 'simple_switch'),
            'json_path': self.compilar_comutador(),
            'thrift_port': None,
            'pcap_dump': getattr(TopologiaTransporte5G, 'capturar_pacotes', False),
            'log_console': True,
            'verbose': False
        }

        c1 = self.addSwitch('c1', **argumentos_comutador)
        c2 = self.addSwitch('c2', **argumentos_comutador)
        c3 = self.addSwitch('c3', **argumentos_comutador)
        c4 = self.addSwitch('c4', **argumentos_comutador)

        h_urllc_1 = self.addHost('h_urllc_1', ip='10.0.1.10/16', mac='00:00:00:00:01:10', defaultRoute='via 10.0.1.1')
        h_embb_1 = self.addHost('h_embb_1', ip='10.0.2.10/16', mac='00:00:00:00:02:10', defaultRoute='via 10.0.2.1')
        h_embb_2 = self.addHost('h_embb_2', ip='10.0.3.10/16', mac='00:00:00:00:03:10', defaultRoute='via 10.0.3.1')
        h_urllc_2 = self.addHost('h_urllc_2', ip='10.0.4.10/16', mac='00:00:00:00:04:10', defaultRoute='via 10.0.4.1')

        self.addLink(h_urllc_1, c1, port2=2)
        self.addLink(h_embb_1, c2, port2=3)
        self.addLink(h_embb_2, c3, port2=3)
        self.addLink(h_urllc_2, c4, port2=2)

        self.addLink(c1, c2, port1=1, port2=1)
        self.addLink(c2, c3, port1=2, port2=1)
        self.addLink(c3, c4, port1=2, port2=1)

    def compilar_comutador(self):
        caminho_json = os.path.join(os.path.dirname(CAMINHO_COMUTADOR), 'comutador.json')
        if not os.path.exists(caminho_json):
            info('Compilando programa P4...\n')
            comando = 'p4c-bm2-ss --std p4-16 -o {} {}'.format(caminho_json, CAMINHO_COMUTADOR)
            if os.system(comando) != 0:
                raise Exception('Falha ao compilar o programa P4')
        return caminho_json

def configurar_tabelas(rede):
    for comutador in rede.switches:
        nome = comutador.name
        caminho_tabela = os.path.join(CAMINHO_TABELAS, '{}.txt'.format(nome))
        if os.path.exists(caminho_tabela):
            info('Configurando tabelas em {}\n'.format(nome))
            os.system('simple_switch_CLI --thrift-port {} < {}'.format(comutador.thrift_port, caminho_tabela))

def configurar_arp_hosts(rede):
    mapeamento_arp = {
        'h_urllc_1': ('10.0.1.1', '00:00:00:00:01:01'),
        'h_embb_1': ('10.0.2.1', '00:00:00:00:02:01'),
        'h_embb_2': ('10.0.3.1', '00:00:00:00:03:01'),
        'h_urllc_2': ('10.0.4.1', '00:00:00:00:04:01')
    }
    for nome_host, host in rede.items():
        if nome_host in mapeamento_arp:
            gateway, mac = mapeamento_arp[nome_host]
            info('Configurando ARP estatico em {} para {} -> {}\n'.format(nome_host, gateway, mac))
            host.setARP(gateway, mac)

def executar():
    parser = argparse.ArgumentParser(description='Topologia de rede de transporte 5G com switches P4')
    parser.add_argument('--comportamento', dest='caminho_comportamento', default='simple_switch', help='Caminho do executavel do switch P4')
    parser.add_argument('--pcap-dump', dest='capturar_pacotes', action='store_true', help='Habilita captura de pacotes')
    parser.add_argument('--cli', dest='abrir_cli', action='store_true', help='Abre o CLI do Mininet apos a inicializacao')
    argumentos = parser.parse_args()

    setLogLevel('info')

    TopologiaTransporte5G.caminho_comportamento = argumentos.caminho_comportamento
    TopologiaTransporte5G.capturar_pacotes = argumentos.capturar_pacotes
    rede = Mininet(topo=TopologiaTransporte5G(), host=P4Host, switch=P4Switch, controller=None)
    rede.start()
    configurar_arp_hosts(rede)
    configurar_tabelas(rede)

    if argumentos.abrir_cli:
        CLI(rede)

    rede.stop()

if __name__ == '__main__':
    executar()
