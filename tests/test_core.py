import unittest

from simple_mailbox_address import MailboxAddress, MailboxParseError


class TestParse(unittest.TestCase):

    def test_simple_angle_addr(self):
        m = MailboxAddress.parse("<alice@work.example>")
        self.assertIsNone(m.display_name)
        self.assertEqual(m.local_part, "alice")
        self.assertEqual(m.domain, "work.example")
        self.assertEqual(m.comments, [])
        self.assertEqual(m.addr_spec, "alice@work.example")

    def test_unquoted_display_name(self):
        m = MailboxAddress.parse("Alice Adams <alice@work.example>")
        self.assertEqual(m.display_name, "Alice Adams")
        self.assertEqual(m.local_part, "alice")
        self.assertEqual(m.domain, "work.example")

    def test_quoted_display_name(self):
        m = MailboxAddress.parse('"Alice Adams" <alice@work.example>')
        self.assertEqual(m.display_name, "Alice Adams")

    def test_quoted_display_name_with_comma(self):
        m = MailboxAddress.parse('"Adams, Alice" <alice@work.example>')
        self.assertEqual(m.display_name, "Adams, Alice")

    def test_quoted_local_part(self):
        m = MailboxAddress.parse('"foo.bar"@work.example')
        self.assertEqual(m.local_part, "foo.bar")
        self.assertEqual(m.domain, "work.example")
        self.assertIsNone(m.display_name)

    def test_quoted_local_part_with_specials(self):
        m = MailboxAddress.parse('"a\\"b"@work.example')
        self.assertEqual(m.local_part, 'a"b')

    def test_dot_local_part(self):
        m = MailboxAddress.parse("first.last@work.example")
        self.assertEqual(m.local_part, "first.last")

    def test_trailing_comment(self):
        m = MailboxAddress.parse("<alice@work.example> (verified)")
        self.assertEqual(m.comments, ["verified"])

    def test_leading_comment(self):
        m = MailboxAddress.parse("(external) alice@work.example")
        self.assertEqual(m.comments, ["external"])
        self.assertIsNone(m.display_name)

    def test_nested_comment(self):
        m = MailboxAddress.parse("<alice@work.example> (outer (inner))")
        self.assertEqual(m.comments, ["outer (inner)"])

    def test_folding_whitespace_between_tokens(self):
        m = MailboxAddress.parse("Alice\r\n Adams <alice@work.example>")
        self.assertEqual(m.display_name, "Alice Adams")

    def test_folding_whitespace_in_angle_addr(self):
        m = MailboxAddress.parse("<alice\r\n @work.example>")
        self.assertEqual(m.local_part, "alice")
        self.assertEqual(m.domain, "work.example")

    def test_addr_spec_property(self):
        m = MailboxAddress.parse('<"foo bar"@work.example>')
        self.assertEqual(m.addr_spec, "foo bar@work.example")

    def test_invalid_no_angle_bracket_after_atom(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse("alice work.example")

    def test_invalid_trailing_data(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse("<alice@work.example> junk")

    def test_invalid_empty_local_part(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse("<@work.example>")

    def test_invalid_single_label_domain(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse("<alice@localhost>")

    def test_invalid_unterminated_quote(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse('"unterminated <alice@work.example>')

    def test_invalid_null_byte(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse("alice\u0000@work.example")

    def test_non_string_input(self):
        with self.assertRaises(MailboxParseError):
            MailboxAddress.parse(123)  # type: ignore[arg-type]

    def test_domain_literal_preserved(self):
        m = MailboxAddress.parse("<alice@[127.0.0.1]>")
        self.assertEqual(m.domain, "[127.0.0.1]")
        self.assertEqual(m.addr_spec, "alice@[127.0.0.1]")


if __name__ == "__main__":
    unittest.main()
