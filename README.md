# simple-mailbox-address

Parses RFC 5322 mailbox address specifications, extracting display names, local parts, domains, comments, and folding whitespace.

## Usage

```python
from simple_mailbox_address import MailboxAddress

m = MailboxAddress.parse('"Alice Adams" <alice@work.example> (verified)')
print(m.display_name)   # Alice Adams
print(m.local_part)      # alice
print(m.domain)          # work.example
print(m.comments)        # ['verified']
print(m.addr_spec)       # alice@work.example
```

`MailboxAddress.parse(text)` returns a `MailboxAddress` instance or raises `MailboxParseError`. The instance exposes `display_name` (or `None`), `local_part`, `domain`, `comments` (a list), and the reconstructed `addr_spec`.

## Why

General-purpose header parsers try to fold multiple addresses, groups, and trace fields into one API surface. That breadth makes the common single-mailbox case awkward to reason about and harder to test exhaustively. This library deliberately handles only a single `mailbox` production — the display name, angle-addr, local part, domain, comments, and the folding whitespace between them. Everything that is not a mailbox (bare `group` syntax, multiple comma-separated mailboxes, trace headers) is rejected so the caller sees a clear boundary.

The trade-off: if your input is a full `To:` header with several recipients, split on commas first — but note that commas inside quoted strings or comments are not separators, so you will need a smarter splitter or a different library.

## Edge cases

- Quoted local parts (`"foo\.bar"@example`) preserve their internal content; surrounding quotes are removed.
- Backslash-pairs inside quoted strings (`"a\"b"`) are unescaped.
- Comments may nest and may appear before the display name, inside the angle brackets, or after the closing bracket. They are collected in source order.
- Folding whitespace (CRLF + spaces) is permitted anywhere ordinary whitespace is. Use `fold_if_present=True` (the default) to collapse it to single spaces.
