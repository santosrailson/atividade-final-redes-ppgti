#!/usr/bin/env python3

import argparse
import time
import sys
import os

from scapy.all import (
    Ether, IP, TCP, Raw, send, sniff, sr1, get_if_addr, get_if_hwaddr
)

PORTA_URLLC = 5000
LIMIAR_LATENCIA_NS = 5_000_000

MACS_GATEWAY = {
    '10.0.1.1': '00:00:00:00:01:01',
    '10.0.2.1': '00:00:00:00:02:01',
    '10.0.3.1': '00:00:00:00:03:01',
    '10.0.4.1': '00:00:00:00:04:01',
}

MACS_HOSTS = {
    '10.0.1.10': '00:00:00:00:01:10',
    '10.0.2.10': '00:00:00:00:02:10',
    '10.0.3.10': '00:00:00:00:03:10',
    '10.0.4.10': '00:00:00:00:04:10',
}


def obter_interface():
    interfaces = os.listdir('/sys/class/net/')
    for nome in interfaces:
        if nome != 'lo' and not nome.startswith('veth'):
            return nome
    return interfaces[0]


def obter_gateway(endereco_ip):
    partes = endereco_ip.split('.')
    return '.'.join(partes[:3] + ['1'])


def construir_pacote(interface, origem, destino, porta_destino, timestamp_ns, dados=b''):
    mac_origem = get_if_hwaddr(interface)
    mac_destino = MACS_HOSTS.get(destino, MACS_GATEWAY.get(obter_gateway(origem), 'ff:ff:ff:ff:ff:ff'))
    payload = str(timestamp_ns).encode() + b'|' + dados

    pacote = Ether(src=mac_origem, dst=mac_destino)
    pacote /= IP(src=origem, dst=destino, tos=46 << 2)
    pacote /= TCP(sport=porta_destino, dport=porta_destino, flags='PA')
    pacote /= Raw(load=payload)
    return pacote


def executar_gerador(endereco_origem, endereco_destino, intervalo_segundos, quantidade):
    interface = obter_interface()
    contador = 0

    while quantidade == 0 or contador < quantidade:
        timestamp_envio = time.time_ns()
        pacote = construir_pacote(interface, endereco_origem, endereco_destino, PORTA_URLLC, timestamp_envio)
        send(pacote, verbose=False, iface=interface)
        contador += 1
        print('PACOTE_ENVIADO seq={} destino={} timestamp={}'.format(contador, endereco_destino, timestamp_envio))
        time.sleep(intervalo_segundos)


def responder_pacote(interface, pacote_recebido):
    ip_recebido = pacote_recebido[IP]
    tcp_recebido = pacote_recebido[TCP]
    payload_recebido = pacote_recebido[Raw].load
    mac_destino = MACS_HOSTS.get(ip_recebido.src, 'ff:ff:ff:ff:ff:ff')
    mac_origem = get_if_hwaddr(interface)

    resposta = Ether(src=mac_origem, dst=mac_destino)
    resposta /= IP(src=ip_recebido.dst, dst=ip_recebido.src, tos=46 << 2)
    resposta /= TCP(sport=tcp_recebido.dport, dport=tcp_recebido.sport, flags='PA', seq=tcp_recebido.ack, ack=tcp_recebido.seq + len(payload_recebido))
    resposta /= Raw(load=payload_recebido)
    send(resposta, verbose=False, iface=interface)


def processar_pacote_recebido(pacote):
    if not pacote.haslayer(TCP) or not pacote.haslayer(Raw):
        return

    tcp = pacote[TCP]
    if tcp.dport != PORTA_URLLC and tcp.sport != PORTA_URLLC:
        return

    payload = pacote[Raw].load.decode(errors='ignore')
    partes = payload.split('|')
    if not partes:
        return

    try:
        timestamp_envio = int(partes[0])
    except ValueError:
        return

    timestamp_recebimento = time.time_ns()
    latencia_ns = timestamp_recebimento - timestamp_envio
    latencia_ms = latencia_ns / 1_000_000.0
    alerta = 'ALERTA_LIMIAR' if latencia_ns > LIMIAR_LATENCIA_NS else 'OK'

    print('PACOTE_RECEBIDO origem={} latencia_ns={} latencia_ms={:.3f} status={}'.format(
        pacote[IP].src, latencia_ns, latencia_ms, alerta
    ))

    interface = obter_interface()
    responder_pacote(interface, pacote)


def executar_receptor():
    interface = obter_interface()
    os.system('iptables -A INPUT -p tcp --dport {} -j DROP 2>/dev/null'.format(PORTA_URLLC))
    print('RECEPTOR_INICIADO interface={} porta={}'.format(interface, PORTA_URLLC))
    try:
        sniff(iface=interface, filter='tcp port {}'.format(PORTA_URLLC), prn=processar_pacote_recebido, store=False)
    finally:
        os.system('iptables -D INPUT -p tcp --dport {} -j DROP 2>/dev/null'.format(PORTA_URLLC))


def executar_par(endereco_origem, endereco_destino, intervalo_segundos, quantidade):
    interface = obter_interface()
    os.system('iptables -A INPUT -p tcp --dport {} -j DROP 2>/dev/null'.format(PORTA_URLLC))
    contador = 0

    try:
        while quantidade == 0 or contador < quantidade:
            timestamp_envio = time.time_ns()
            pacote = construir_pacote(interface, endereco_origem, endereco_destino, PORTA_URLLC, timestamp_envio)
            resposta = sr1(pacote, verbose=False, iface=interface, timeout=2)

            if resposta and resposta.haslayer(Raw):
                payload = resposta[Raw].load.decode(errors='ignore')
                partes = payload.split('|')
                try:
                    timestamp_ida = int(partes[0])
                except ValueError:
                    timestamp_ida = timestamp_envio

                timestamp_chegada = time.time_ns()
                rtt_ns = timestamp_chegada - timestamp_ida
                rtt_ms = rtt_ns / 1_000_000.0
                alerta = 'ALERTA_LIMIAR' if rtt_ns > LIMIAR_LATENCIA_NS else 'OK'
                print('RESPOSTA_RECEBIDA seq={} rtt_ns={} rtt_ms={:.3f} status={}'.format(
                    contador + 1, rtt_ns, rtt_ms, alerta
                ))
            else:
                print('RESPOSTA_NAO_RECEBIDA seq={}'.format(contador + 1))

            contador += 1
            time.sleep(intervalo_segundos)
    finally:
        os.system('iptables -D INPUT -p tcp --dport {} -j DROP 2>/dev/null'.format(PORTA_URLLC))


def principal():
    parser = argparse.ArgumentParser(description='Geracao e medicao de trafego uRLLC com Scapy')
    parser.add_argument('--modo', choices=['gerador', 'receptor', 'par'], required=True,
                        help='Modo de execucao: gerador, receptor ou par')
    parser.add_argument('--origem', default=get_if_addr(obter_interface()),
                        help='Endereco IP de origem')
    parser.add_argument('--destino', help='Endereco IP de destino')
    parser.add_argument('--intervalo', type=float, default=1.0,
                        help='Intervalo entre pacotes em segundos')
    parser.add_argument('--quantidade', type=int, default=0,
                        help='Quantidade de pacotes a enviar (0 = infinito)')
    argumentos = parser.parse_args()

    if argumentos.modo in ['gerador', 'par'] and not argumentos.destino:
        parser.error('--destino e obrigatorio para os modos gerador e par')

    if argumentos.modo == 'gerador':
        executar_gerador(argumentos.origem, argumentos.destino, argumentos.intervalo, argumentos.quantidade)
    elif argumentos.modo == 'receptor':
        executar_receptor()
    elif argumentos.modo == 'par':
        executar_par(argumentos.origem, argumentos.destino, argumentos.intervalo, argumentos.quantidade)


if __name__ == '__main__':
    principal()
