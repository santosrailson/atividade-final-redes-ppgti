#!/usr/bin/env python3
"""
Corrige na origem o aviso:

    *** Error setting resource limits. Mininet's performance may be affected.

A funcao mininet.util.fixLimits() tenta ajustar 12 parametros do
kernel (ulimits + sysctls) para suportar topologias grandes, todos
dentro de um unico bloco try/except: se qualquer um falhar, os
demais nem chegam a ser tentados, e essa mensagem generica aparece
sem dizer qual item falhou.

Dentro da VM Linux do Docker Desktop for Mac, 6 desses 12 ajustes
sempre falham (testado e confirmado neste projeto):

  - net.core.wmem_max / net.core.rmem_max
      -> PermissionError: sysctls de rede nao-namespaced, cuja
         escrita o Docker bloqueia mesmo em modo --privileged.
  - net.core.netdev_max_backlog, net.ipv4.neigh.default.gc_thresh{1,2,3},
    net.ipv4.route.max_size
      -> FileNotFoundError: esses arquivos /proc/sys nem existem no
         kernel enxuto da VM do Docker Desktop.

Nenhum desses 6 ajustes faz diferenca para a topologia deste projeto
(4 switches, 4 hosts, trafego na casa dos Mbps) -- eles existem para
topologias com centenas/milhares de hosts. Os outros 6 ajustes (limite
de processos/arquivos abertos, buffers TCP, PTYs) funcionam
normalmente neste ambiente e continuam sendo aplicados.

Este script substitui o corpo de fixLimits() por uma versao que
isola cada ajuste em seu proprio try/except: os que funcionam sao
aplicados de verdade (antes nunca eram, pois o bloco abortava no
primeiro fracasso); os que nao podem funcionar aqui falham em
silencio, sem imprimir o aviso.

Rodado uma unica vez durante o build da imagem Docker (ver
Dockerfile) -- nao e executado em tempo de experimento.
"""
import sys

CAMINHO = "/usr/lib/python3/dist-packages/mininet/util.py"

ANTIGO = '''def fixLimits():
    "Fix ridiculously small resource limits."
    debug( "*** Setting resource limits\\n" )
    try:
        rlimitTestAndSet( RLIMIT_NPROC, 8192 )
        rlimitTestAndSet( RLIMIT_NOFILE, 16384 )
        # Increase open file limit
        sysctlTestAndSet( 'fs.file-max', 10000 )
        # Increase network buffer space
        sysctlTestAndSet( 'net.core.wmem_max', 16777216 )
        sysctlTestAndSet( 'net.core.rmem_max', 16777216 )
        sysctlTestAndSet( 'net.ipv4.tcp_rmem', '10240 87380 16777216' )
        sysctlTestAndSet( 'net.ipv4.tcp_wmem', '10240 87380 16777216' )
        sysctlTestAndSet( 'net.core.netdev_max_backlog', 5000 )
        # Increase arp cache size
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh1', 4096 )
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh2', 8192 )
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh3', 16384 )
        # Increase routing table size
        sysctlTestAndSet( 'net.ipv4.route.max_size', 32768 )
        # Increase number of PTYs for nodes
        sysctlTestAndSet( 'kernel.pty.max', 20000 )
    # pylint: disable=broad-except
    except Exception:
        warn( "*** Error setting resource limits. "
              "Mininet's performance may be affected.\\n" )
    # pylint: enable=broad-except'''

NOVO = '''def fixLimits():
    "Fix ridiculously small resource limits."
    debug( "*** Setting resource limits\\n" )
    # Cada ajuste isolado em seu proprio try/except: em ambientes
    # restritos (ex.: VM do Docker Desktop for Mac), alguns sysctls de
    # rede nao-namespaced nao podem ser escritos ou nem existem: isso
    # nao deve impedir os demais ajustes (ulimits, buffers TCP, PTYs)
    # de serem aplicados normalmente, nem gerar um aviso assustador
    # para algo que nao afeta topologias pequenas.
    # pylint: disable=broad-except
    ajustes = [
        lambda: rlimitTestAndSet( RLIMIT_NPROC, 8192 ),
        lambda: rlimitTestAndSet( RLIMIT_NOFILE, 16384 ),
        lambda: sysctlTestAndSet( 'fs.file-max', 10000 ),
        lambda: sysctlTestAndSet( 'net.core.wmem_max', 16777216 ),
        lambda: sysctlTestAndSet( 'net.core.rmem_max', 16777216 ),
        lambda: sysctlTestAndSet( 'net.ipv4.tcp_rmem', '10240 87380 16777216' ),
        lambda: sysctlTestAndSet( 'net.ipv4.tcp_wmem', '10240 87380 16777216' ),
        lambda: sysctlTestAndSet( 'net.core.netdev_max_backlog', 5000 ),
        lambda: sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh1', 4096 ),
        lambda: sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh2', 8192 ),
        lambda: sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh3', 16384 ),
        lambda: sysctlTestAndSet( 'net.ipv4.route.max_size', 32768 ),
        lambda: sysctlTestAndSet( 'kernel.pty.max', 20000 ),
    ]
    falhas = 0
    for ajuste in ajustes:
        try:
            ajuste()
        except Exception:
            falhas += 1
    if falhas:
        debug( "*** %d de %d ajustes de limite de recursos nao "
               "puderam ser aplicados neste ambiente (normal em VMs "
               "restritas); os demais foram aplicados normalmente.\\n"
               % ( falhas, len( ajustes ) ) )
    # pylint: enable=broad-except'''

with open(CAMINHO, "r") as arquivo:
    conteudo = arquivo.read()

ocorrencias = conteudo.count(ANTIGO)
if ocorrencias != 1:
    sys.exit(
        "Esperava exatamente 1 ocorrencia do corpo de fixLimits() em %s, "
        "encontrei %d. A versao do Mininet instalada pode ter mudado o "
        "codigo-fonte -- ajuste o texto ANTIGO/NOVO deste script antes "
        "de prosseguir." % (CAMINHO, ocorrencias)
    )

conteudo = conteudo.replace(ANTIGO, NOVO)
with open(CAMINHO, "w") as arquivo:
    arquivo.write(conteudo)

print("mininet/util.py corrigido: fixLimits() agora isola cada ajuste.")
