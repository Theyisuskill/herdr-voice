"""Protocol input must remain a paste, never a submitted command."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targeted_paste import PasteConnection, PasteUnavailable


class PasteTests(unittest.TestCase):
    def connection(self):
        connection = PasteConnection.__new__(PasteConnection)
        connection.channel = 12
        connection.send = Mock()
        return connection

    def test_unicode_and_newline_are_bracketed_without_return_key(self):
        connection = self.connection()
        connection.paste('Odoo, acción\nsegunda línea')
        connection.send.assert_called_once_with(12, 0, b'\x1b[200~' + 'Odoo, acción\nsegunda línea'.encode() + b'\x1b[201~')

    def test_control_characters_cannot_escape_paste(self):
        connection = self.connection()
        connection.paste('hola\x1b[201~\r\x03mundo')
        payload = connection.send.call_args.args[2]
        self.assertEqual(payload.count(b'\x1b'), 2)
        self.assertNotIn(b'\r', payload)
        self.assertNotIn(b'\x03', payload)

    def test_oversized_text_is_not_sent(self):
        connection = self.connection()
        with self.assertRaises(PasteUnavailable): connection.paste('a' * (128 * 1024 + 1))
        connection.send.assert_not_called()


if __name__ == '__main__': unittest.main()
