#include <core.p4>
#include <v1model.p4>

const bit<16> TIPO_ETHERNET_IPV4 = 0x0800;
const bit<8> PROTOCOLO_IPV4_TCP = 0x06;

header ethernete_t {
    bit<48> endereco_destino;
    bit<48> endereco_origem;
    bit<16> tipo;
}

header ipv4_t {
    bit<4> versao;
    bit<4> tamanho_cabecalho;
    bit<8> servicos_diferenciados;
    bit<16> tamanho_total;
    bit<16> identificacao;
    bit<3> flags;
    bit<13> deslocamento_fragmento;
    bit<8> tempo_vida;
    bit<8> protocolo;
    bit<16> soma_verificacao_cabecalho;
    bit<32> endereco_origem;
    bit<32> endereco_destino;
}

header tcp_t {
    bit<16> porta_origem;
    bit<16> porta_destino;
    bit<32> numero_sequencia;
    bit<32> numero_reconhecimento;
    bit<4> tamanho_cabecalho;
    bit<3> reservado;
    bit<9> flags;
    bit<16> tamanho_janela;
    bit<16> soma_verificacao;
    bit<16> ponteiro_urgencia;
}

struct metadados_t {
    bit<9> porta_entrada;
    bit<9> porta_saida;
    bit<32> endereco_ipv4_origem;
    bit<32> endereco_ipv4_destino;
    bit<16> porta_tcp_destino;
    bit<3> classe_prioridade;
}

struct pacotes_t {
    ethernete_t ethernete;
    ipv4_t ipv4;
    tcp_t tcp;
}

parser parser_principal(packet_in pacote, out pacotes_t cabecalhos, inout metadados_t metadados, inout standard_metadata_t metadados_padrao) {
    state start {
        pacote.extract(cabecalhos.ethernete);
        transition select(cabecalhos.ethernete.tipo) {
            TIPO_ETHERNET_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        pacote.extract(cabecalhos.ipv4);
        transition select(cabecalhos.ipv4.protocolo) {
            PROTOCOLO_IPV4_TCP: parse_tcp;
            default: accept;
        }
    }

    state parse_tcp {
        pacote.extract(cabecalhos.tcp);
        transition accept;
    }
}

control verificador_soma(inout pacotes_t cabecalhos, inout metadados_t metadados) {
    apply {
        if (cabecalhos.ipv4.versao == 4w4) {
            update_checksum(cabecalhos.ipv4.isValid(),
                { cabecalhos.ipv4.versao,
                  cabecalhos.ipv4.tamanho_cabecalho,
                  cabecalhos.ipv4.servicos_diferenciados,
                  cabecalhos.ipv4.tamanho_total,
                  cabecalhos.ipv4.identificacao,
                  cabecalhos.ipv4.flags,
                  cabecalhos.ipv4.deslocamento_fragmento,
                  cabecalhos.ipv4.tempo_vida,
                  cabecalhos.ipv4.protocolo,
                  cabecalhos.ipv4.endereco_origem,
                  cabecalhos.ipv4.endereco_destino },
                cabecalhos.ipv4.soma_verificacao_cabecalho,
                HashAlgorithm.csum16);
        }
    }
}

control processamento_ingresso(inout pacotes_t cabecalhos, inout metadados_t metadados, inout standard_metadata_t metadados_padrao) {
    action classificar_urllc() {
        metadados.classe_prioridade = 3w7;
        cabecalhos.ipv4.servicos_diferenciados = 8w46;
    }

    action classificar_embb() {
        metadados.classe_prioridade = 3w1;
        cabecalhos.ipv4.servicos_diferenciados = 8w0;
    }

    action encaminhar(bit<9> porta_saida, bit<48> proximo_salto_mac) {
        metadados_padrao.egress_spec = porta_saida;
        cabecalhos.ethernete.endereco_destino = proximo_salto_mac;
        cabecalhos.ipv4.tempo_vida = cabecalhos.ipv4.tempo_vida - 1;
    }

    action descartar() {
        mark_to_drop(metadados_padrao);
    }

    table tabela_classificacao {
        key = {
            cabecalhos.ipv4.endereco_origem: exact;
            cabecalhos.tcp.porta_destino: exact;
        }
        actions = {
            classificar_urllc;
            classificar_embb;
            NoAction;
        }
        size = 64;
        default_action = NoAction();
    }

    table tabela_encaminhamento_ipv4 {
        key = {
            cabecalhos.ipv4.endereco_destino: lpm;
        }
        actions = {
            encaminhar;
            descartar;
            NoAction;
        }
        size = 128;
        default_action = descartar();
    }

    apply {
        if (cabecalhos.ipv4.isValid() && cabecalhos.tcp.isValid()) {
            metadados.endereco_ipv4_origem = cabecalhos.ipv4.endereco_origem;
            metadados.endereco_ipv4_destino = cabecalhos.ipv4.endereco_destino;
            metadados.porta_tcp_destino = cabecalhos.tcp.porta_destino;

            tabela_classificacao.apply();
            tabela_encaminhamento_ipv4.apply();
        } else if (cabecalhos.ipv4.isValid()) {
            tabela_encaminhamento_ipv4.apply();
        }
    }
}

control processamento_egresso(inout pacotes_t cabecalhos, inout metadados_t metadados, inout standard_metadata_t metadados_padrao) {
    apply { }
}

control deparser_principal(packet_out pacote, in pacotes_t cabecalhos) {
    apply {
        pacote.emit(cabecalhos.ethernete);
        pacote.emit(cabecalhos.ipv4);
        pacote.emit(cabecalhos.tcp);
    }
}

V1Switch(parser_principal(), verificador_soma(), processamento_ingresso(), processamento_egresso(), deparser_principal()) main;
