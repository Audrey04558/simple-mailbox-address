"""Parser for a single RFC 5322 mailbox production.

Scope: ONE mailbox, not a comma-separated list and not a group.
Splitting a multi-recipient header on commas is the caller's job,
but only safe when no comma sits inside a quoted string or comment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class MailboxParseError(ValueError):
    """Raised when text does not contain exactly one valid mailbox."""


@dataclass(frozen=True)
class MailboxAddress:
    """A single RFC 5322 mailbox address.

    Attributes:
        display_name: Display name with whitespace collapsed and RFC 5322
            quoted-string content unescaped, or None when no display name
            was present.
        local_part: Local part with surrounding quotes removed and
            backslash-pairs unescaped.
        domain: Domain (no brackets).
        comments: Comments encountered, outer parentheses removed,
            nesting flattened to the source text of each comment.
    """

    display_name: Optional[str]
    local_part: str
    domain: str
    comments: List[str] = field(default_factory=list)

    @property
    def addr_spec(self) -> str:
        return f"{self.local_part}@{self.domain}"

    @classmethod
    def parse(cls, text: str, *, fold_if_present: bool = True) -> "MailboxAddress":
        """Parse a single mailbox production.

        Args:
            text: Raw input.
            fold_if_present: When True (default), collapse folding
                whitespace (CRLF + linear whitespace) to single spaces
                and require it to appear only at legal fold points.
        """
        if not isinstance(text, str):
            raise MailboxParseError("text must be a string")
        if "\u0000" in text:
            raise MailboxParseError("null bytes are not permitted")
        parser = _MailboxParser(text, fold_if_present=fold_if_present)
        return parser.parse()


class _MailboxParser:
    """Hand-written recursive-descent reader for one mailbox.

    Index-based rather than regex so that comment nesting, quoted-pair
    unescaping, and folding-whitespace handling share a single pass.
    """

    _UNQUOTED_EXTRA = "!#$%&'*+-/=?^_`{|}~"

    def __init__(self, text: str, *, fold_if_present: bool) -> None:
        self._s = text
        self._i = 0
        self._n = len(text)
        self._fold = fold_if_present
        self._comments: List[str] = []

    # -- entry point -------------------------------------------------

    def parse(self) -> MailboxAddress:
        self._cfws()  # leading comments / whitespace
        if self._at_angle_addr():
            return self._angle_addr(None)
        # Try to read a display name, then expect '<'.
        display_name = self._read_display_name()
        self._cfws()
        if self._at_angle_addr():
            return self._angle_addr(display_name)
        # No angle-addr followed: the "display name" might actually
        # be a bare addr-spec (e.g. alice@work.example).
        if display_name is not None and self._peek() == "@":
            return self._bare_addr_spec(display_name)
        raise MailboxParseError("expected a '<' after the display name")

    def _at_angle_addr(self) -> bool:
        return self._peek() == "<"

    def _bare_addr_spec(self, local_part: str) -> MailboxAddress:
        self._i += 1  # consume '@'
        domain = self._domain()
        self._cfws()  # trailing comments / whitespace
        if self._i != self._n:
            raise MailboxParseError("trailing characters after addr-spec")
        return MailboxAddress(
            display_name=None,
            local_part=local_part,
            domain=domain,
            comments=list(self._comments),
        )

    # -- display name ------------------------------------------------

    def _read_display_name(self) -> Optional[str]:
        if self._peek() == '"':
            return self._quoted_string()
        # An unquoted display name is one or more atoms separated by
        # linear whitespace. We require at least one atom so that stray
        # whitespace alone never becomes an empty display name.
        parts: List[str] = []
        while True:
            self._cfws_internal()
            atom = self._atom_or_none()
            if atom is None:
                break
            parts.append(atom)
            if self._peek() == "@":
                return "".join(parts)
        if not parts:
            return None
        return " ".join(parts)

    def _atom_or_none(self) -> Optional[str]:
        start = self._i
        while self._i < self._n:
            c = self._s[self._i]
            if c == "." or c.isalnum() or c in self._UNQUOTED_EXTRA:
                self._i += 1
            else:
                break
        if self._i == start:
            return None
        return self._s[start:self._i]

    # -- angle-addr --------------------------------------------------

    def _angle_addr(self, display_name: Optional[str]) -> MailboxAddress:
        assert self._s[self._i] == "<"
        self._i += 1
        self._cfws_internal()
        local_part = self._local_part()
        self._cfws_internal()
        if self._peek() != "@":
            raise MailboxParseError("missing '@' in angle-addr local part")
        self._i += 1
        domain = self._domain()
        self._cfws_internal()
        if self._peek() != ">":
            raise MailboxParseError("missing closing '>'")
        self._i += 1
        self._cfws()  # trailing comments / whitespace
        if self._i != self._n:
            raise MailboxParseError("trailing characters after closing '>'")
        return MailboxAddress(
            display_name=display_name,
            local_part=local_part,
            domain=domain,
            comments=list(self._comments),
        )

    def _local_part(self) -> str:
        if self._peek() == '"':
            return self._quoted_string()
        start = self._i
        while self._i < self._n:
            c = self._s[self._i]
            if c == "." or c.isalnum() or c in self._UNQUOTED_EXTRA:
                self._i += 1
            else:
                break
        if self._i == start:
            raise MailboxParseError("empty local part")
        return self._s[start:self._i]

    def _domain(self) -> str:
        if self._peek() == "[":
            return self._domain_literal()
        labels: List[str] = []
        while True:
            label = self._domain_label()
            if not label:
                raise MailboxParseError("empty domain label")
            labels.append(label)
            if self._peek() != ".":
                break
            self._i += 1
        if len(labels) == 1:
            raise MailboxParseError("domain must have at least two labels")
        if labels and labels[-1] == "":
            raise MailboxParseError("trailing dot in domain")
        return ".".join(labels)

    def _domain_label(self) -> str:
        start = self._i
        while self._i < self._n:
            c = self._s[self._i]
            if c == "-" or c.isalnum():
                self._i += 1
            else:
                break
        return self._s[start:self._i]

    def _domain_literal(self) -> str:
        assert self._s[self._i] == "["
        start = self._i
        self._i += 1
        while self._i < self._n:
            c = self._s[self._i]
            if c == "\\":
                self._i += 2
                continue
            if c == "]":
                self._i += 1
                return self._s[start:self._i]
            self._i += 1
        raise MailboxParseError("unterminated domain literal")

    # -- quoted string ----------------------------------------------

    def _quoted_string(self) -> str:
        assert self._s[self._i] == '"'
        self._i += 1
        out: List[str] = []
        while self._i < self._n:
            c = self._s[self._i]
            if c == "\\":
                nxt = self._i + 1
                if nxt >= self._n:
                    raise MailboxParseError("dangling backslash")
                out.append(self._s[nxt])
                self._i = nxt + 1
                continue
            if c == '"':
                self._i += 1
                return "".join(out)
            if c == "\r":
                nxt = self._i + 1
                if nxt < self._n and self._s[nxt] == "\n":
                    self._i = nxt + 1
                    continue
                raise MailboxParseError("bare CR inside quoted string")
            out.append(c)
            self._i += 1
        raise MailboxParseError("unterminated quoted string")

    # -- CFWS --------------------------------------------------------

    def _cfws(self) -> None:
        self._cfws_internal(consume_trailing_ws=True)

    def _cfws_internal(self, *, consume_trailing_ws: bool = False) -> None:
        while True:
            consumed_ws = self._lwsp(consume_trailing_ws=consume_trailing_ws)
            consumed_comment = self._comment_if_present()
            if not consumed_ws and not consumed_comment:
                break

    def _comment_if_present(self) -> bool:
        if self._peek() != "(":
            return False
        self._comments.append(self._comment())
        return True

    def _comment(self) -> str:
        assert self._s[self._i] == "("
        self._i += 1
        out: List[str] = []
        depth = 1
        while self._i < self._n:
            c = self._s[self._i]
            if c == "\\":
                nxt = self._i + 1
                if nxt >= self._n:
                    raise MailboxParseError("dangling backslash in comment")
                out.append(self._s[nxt])
                self._i = nxt + 1
                continue
            if c == "(":
                depth += 1
                out.append(c)
                self._i += 1
                continue
            if c == ")":
                depth -= 1
                self._i += 1
                if depth == 0:
                    return "".join(out)
                out.append(c)
                continue
            if c == "\r":
                nxt = self._i + 1
                if nxt < self._n and self._s[nxt] == "\n":
                    self._i = nxt + 1
                    continue
                raise MailboxParseError("bare CR inside comment")
            out.append(c)
            self._i += 1
        raise MailboxParseError("unterminated comment")

    def _lwsp(self, *, consume_trailing_ws: bool) -> bool:
        consumed = False
        while self._i < self._n:
            c = self._s[self._i]
            if c in " \t":
                self._i += 1
                consumed = True
                continue
            if c == "\r":
                nxt = self._i + 1
                if nxt >= self._n or self._s[nxt] != "\n":
                    raise MailboxParseError("bare CR outside quoted string")
                nxt2 = nxt + 1
                if nxt2 >= self._n or self._s[nxt2] not in " \t":
                    if consume_trailing_ws:
                        # Folding whitespace MUST be followed by at least
                        # one linear-whitespace character.
                        raise MailboxParseError("folding whitespace must be followed by WSP")
                    self._i = nxt
                    return consumed
                self._i = nxt2 + 1
                consumed = True
                continue
            break
        return consumed

    def _peek(self) -> str:
        if self._i >= self._n:
            return ""
        return self._s[self._i]
