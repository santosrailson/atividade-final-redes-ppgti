import unittest

from protocolo_urllc import (
    TAMANHO_MENSAGEM,
    codificar_mensagem,
    decodificar_mensagem,
    extrair_mensagens,
)


class TestProtocoloUrllc(unittest.TestCase):
    def test_roundtrip(self):
        dados = codificar_mensagem(42, 123.5)
        self.assertEqual(len(dados), TAMANHO_MENSAGEM)
        self.assertEqual(decodificar_mensagem(dados), (42, 123.5))

    def test_fragmentacao_e_agregacao_tcp(self):
        dados = codificar_mensagem(1, 1.0) + codificar_mensagem(2, 2.0)
        mensagens, sobra = extrair_mensagens(dados[:7])
        self.assertEqual(mensagens, [])
        mensagens, sobra = extrair_mensagens(sobra + dados[7:])
        self.assertEqual(mensagens, [(1, 1.0), (2, 2.0)])
        self.assertEqual(sobra, b"")

    def test_magic_invalida(self):
        with self.assertRaises(ValueError):
            decodificar_mensagem(b"XXXX" + b"\x00" * (TAMANHO_MENSAGEM - 4))


if __name__ == "__main__":
    unittest.main()
