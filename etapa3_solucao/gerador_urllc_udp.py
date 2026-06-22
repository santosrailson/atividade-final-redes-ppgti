#!/usr/bin/env python3
"""
Gerador de trafego uRLLC via UDP.

Envia pacotes UDP para o endereco/porta de destino, inserindo um timestamp de
precisao dupla no payload. O pacote e marcado com DSCP 46 (Expedited
Forwarding) para que o switch P4 possa classifica-lo como uRLLC sem precisar
inspecionar portas TCP/UDP.

Uso:
    python3 gerador_urllc_udp.py <ip_destino> <porta> <intervalo_s> <duracao_s>

Exemplo:
    python3 gerador_urllc_udp.py 10.0.3.2 5000 0.5 60
"""

import socket
import struct
import sys
import time

DSCP_URLLC = 46


def configurar_dscp(soquete, dscp):
    # DSCP ocupa os 6 bits mais significativos do campo ToS do IPv4.
    # O socket precisa do valor ToS = DSCP << 2.
    soquete.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp << 2)


def main():
    if len(sys.argv) < 5:
        print("Uso: %s <ip_destino> <porta> <intervalo_s> <duracao_s>" % sys.argv[0])
        sys.exit(1)

    ip_destino = sys.argv[1]
    porta = int(sys.argv[2])
    intervalo = float(sys.argv[3])
    duracao = float(sys.argv[4])

    soquete = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    configurar_dscp(soquete, DSCP_URLLC)

    print("Gerador uRLLC UDP iniciado: %s:%d a cada %.2fs por %.1fs" %
          (ip_destino, porta, intervalo, duracao))

    tempo_inicio = time.time()
    contador = 0
    with open("/tmp/latencias_urllc.csv", "w") as arquivo:
        arquivo.write("latencia_ms\n")
        while time.time() - tempo_inicio < duracao:
            timestamp_envio = time.time()
            payload = struct.pack("!d", timestamp_envio)
            soquete.sendto(payload, (ip_destino, porta))

            # Mede a latencia local de envio (sera substituida pela medicao
            # do receptor; mantida apenas para compatibilidade com o grafico).
            latencia_ms = (time.time() - timestamp_envio) * 1000
            arquivo.write("%.3f\n" % latencia_ms)
            arquivo.flush()
            contador += 1

            time.sleep(intervalo)

    soquete.close()
    print("Gerador uRLLC UDP finalizado. %d pacotes enviados." % contador)


if __name__ == "__main__":
    main()
