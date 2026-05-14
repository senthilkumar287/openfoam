"""
OpenFOAM dictionary parser.

A hand-written recursive-descent parser over a tokenizer. Handles the
features that matter for real OpenFOAM cases:

    - nested dictionaries  { ... }
    - lists                ( ... )
    - vectors / tensors    (x y z) / (xx ... zz)
    - dimensioned values   nu [0 2 -1 0 0 0 0] 1e-5
    - field values         uniform (0 0 0)  /  nonuniform List<vector> N (...)
    - keyword-lists        boundary ( inlet { ... } outlet { ... } );
    - comments             // line  and  /* block */    (preserved as trivia)
    - macros / includes    #include "..."   $variableName   (preserved verbatim)

The parser does NOT validate semantics (that's the Schema layer). It produces
a faithful tree the rest of the system can mutate and serialize.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re

from .ast_nodes import (
    Node, Dict_, Scalar, Vector, Tensor, Dimensioned,
    FieldValue, List_, KeyValueList,
)


# ── Token ─────────────────────────────────────────────────────────────────
@dataclass
class Token:
    kind: str   # "WORD" | "NUMBER" | "STRING" | "LBRACE" | "RBRACE"
                # "LPAREN" | "RPAREN" | "LBRACKET" | "RBRACKET"
                # "SEMI" | "COMMENT" | "DIRECTIVE" | "EOF"
    text: str
    line: int


# ── Tokenizer ─────────────────────────────────────────────────────────────
class Tokenizer:
    """Lexes OpenFOAM source into a token stream. Comments are emitted as
    tokens so the parser can attach them as trivia."""

    _NUM_RE = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")

    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.line = 1

    def tokens(self) -> list[Token]:
        out: list[Token] = []
        while self.pos < len(self.src):
            c = self.src[self.pos]
            if c == "\n":
                self.line += 1
                self.pos += 1
                continue
            if c.isspace():
                self.pos += 1
                continue
            # Comments
            if c == "/" and self._peek(1) == "/":
                end = self.src.find("\n", self.pos)
                if end == -1:
                    end = len(self.src)
                out.append(Token("COMMENT", self.src[self.pos:end], self.line))
                self.pos = end
                continue
            if c == "/" and self._peek(1) == "*":
                end = self.src.find("*/", self.pos + 2)
                if end == -1:
                    end = len(self.src)
                else:
                    end += 2
                txt = self.src[self.pos:end]
                self.line += txt.count("\n")
                out.append(Token("COMMENT", txt, self.line))
                self.pos = end
                continue
            # Directives: #include, #codeStream, etc. — pass through
            if c == "#":
                end = self._scan_directive()
                out.append(Token("DIRECTIVE", self.src[self.pos:end], self.line))
                self.pos = end
                continue
            # Punctuation
            single = {"{": "LBRACE", "}": "RBRACE", "(": "LPAREN", ")": "RPAREN",
                      "[": "LBRACKET", "]": "RBRACKET", ";": "SEMI"}
            if c in single:
                out.append(Token(single[c], c, self.line))
                self.pos += 1
                continue
            # String
            if c == '"':
                end = self.src.find('"', self.pos + 1)
                if end == -1:
                    end = len(self.src)
                out.append(Token("STRING", self.src[self.pos:end + 1], self.line))
                self.pos = end + 1
                continue
            # Number — be careful: minus sign may also begin a word
            m = self._NUM_RE.match(self.src, self.pos)
            if m and self._is_number_context(out):
                out.append(Token("NUMBER", m.group(0), self.line))
                self.pos = m.end()
                continue
            # Word (identifier, keyword, type name, etc.)
            end = self._scan_word()
            out.append(Token("WORD", self.src[self.pos:end], self.line))
            self.pos = end
        out.append(Token("EOF", "", self.line))
        return out

    def _peek(self, offset: int) -> str:
        p = self.pos + offset
        return self.src[p] if p < len(self.src) else ""

    def _scan_word(self) -> int:
        i = self.pos
        # Words can include letters, digits, _, <>, :, ., +/-, but not whitespace
        # or our punctuation set. We stop at any structural char.
        stop = set(" \t\n\r{}();[]\"")
        while i < len(self.src) and self.src[i] not in stop:
            i += 1
        return max(i, self.pos + 1)

    def _scan_directive(self) -> int:
        # Directives span up to end of line, unless they open a block like #{...#}
        end = self.src.find("\n", self.pos)
        if end == -1:
            end = len(self.src)
        return end

    def _is_number_context(self, out: list[Token]) -> bool:
        """A '-' or digit starts a number only when we're in a 'value position':
        after `(`, `[`, a previous NUMBER, or whitespace following a value-like
        token. In OpenFOAM, type names like `kEpsilon` are WORDs even though they
        contain letters, so this only matters for leading-minus disambiguation."""
        if not out:
            return True
        last = out[-1]
        # In list/vector/dimension/value-after-key contexts, treat as number.
        return last.kind in {"LPAREN", "LBRACKET", "NUMBER", "WORD"}


# ── Parser ────────────────────────────────────────────────────────────────
class FoamParser:
    """
    Recursive-descent parser. Entry point: `parse()` → Dict_ (root).
    """

    def __init__(self, src: str):
        self.tokens = Tokenizer(src).tokens()
        self.i = 0
        self._pending_trivia: list[str] = []

    # ── public ────────────────────────────────────────────────────────────
    def parse(self) -> Dict_:
        root = Dict_()
        while self._peek().kind != "EOF":
            self._absorb_trivia(root)
            if self._peek().kind == "EOF":
                break
            self._parse_entry(root)
        return root

    # ── tokens ────────────────────────────────────────────────────────────
    def _peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def _advance(self) -> Token:
        t = self.tokens[self.i]
        self.i += 1
        return t

    def _expect(self, kind: str) -> Token:
        t = self._advance()
        if t.kind != kind:
            raise SyntaxError(
                f"Expected {kind} at line {t.line}, got {t.kind} ({t.text!r})"
            )
        return t

    # ── trivia (comments / directives) ────────────────────────────────────
    def _absorb_trivia(self, dict_node: Dict_) -> None:
        """Collect comments/directives that precede the next real entry.
        They become trivia entries inside the parent dict."""
        while True:
            t = self._peek()
            if t.kind == "COMMENT":
                dict_node.entries.append(("__comment__", t.text))
                self._advance()
            elif t.kind == "DIRECTIVE":
                # Treat directives as opaque entries we preserve verbatim.
                dict_node.entries.append(("__directive__", t.text))
                self._advance()
            else:
                break

    # ── entries ───────────────────────────────────────────────────────────
    def _parse_entry(self, parent: Dict_) -> None:
        """Parse `key value;` or `key { ... }` or `key ( ... );`."""
        key_tok = self._advance()
        if key_tok.kind not in {"WORD", "STRING"}:
            raise SyntaxError(f"Expected key, got {key_tok.kind} at line {key_tok.line}")
        key = key_tok.text

        nxt = self._peek()

        # `key { ... }`  → sub-dictionary
        if nxt.kind == "LBRACE":
            self._advance()
            sub = self._parse_dict_body()
            parent._set_child(key, sub)
            return

        # `key ( ... );` → list OR keyword-list (depends on contents)
        if nxt.kind == "LPAREN":
            node = self._parse_list_or_kvlist()
            self._consume_semi()
            parent._set_child(key, node)
            return

        # Otherwise: value expression terminated by `;`
        value_node = self._parse_value_expr(key)
        self._consume_semi()
        parent._set_child(key, value_node)

    def _parse_dict_body(self) -> Dict_:
        d = Dict_()
        while True:
            self._absorb_trivia(d)
            t = self._peek()
            if t.kind == "RBRACE":
                self._advance()
                return d
            if t.kind == "EOF":
                raise SyntaxError("Unterminated dictionary block")
            self._parse_entry(d)

    # ── value expressions ─────────────────────────────────────────────────
    def _parse_value_expr(self, key: str) -> Node:
        """
        Parses everything between `key ` and `;`. Handles:
          - simple scalar:        `42`  `0.001`  `Euler`  `"some string"`
          - vector / tensor:      `(0 0 -9.81)`
          - dimensioned:          `[0 2 -1 0 0 0 0] 1e-5`
                                   OR `nu [0 2 -1 0 0 0 0] 1e-5`
          - field values:         `uniform (0 0 0)`,
                                   `nonuniform List<vector> 5 ((..))`
          - multi-word values:    `Gauss linear corrected`  (treated as a list-Scalar)
        """
        first = self._peek()

        # uniform / nonuniform
        if first.kind == "WORD" and first.text in ("uniform", "nonuniform"):
            kind = self._advance().text
            if kind == "uniform":
                inner = self._parse_atom()
                return FieldValue(kind="uniform", value=inner)
            # nonuniform List<type> N ( ... )
            list_type = self._advance().text  # e.g. List<vector>
            # Optional count
            if self._peek().kind == "NUMBER":
                self._advance()
            inner = self._parse_atom()
            return FieldValue(kind="nonuniform", list_type=list_type, value=inner)

        # Bare dimensioned: `[0 2 -1 0 0 0 0] 1e-5`
        # OR bare dimensions list (no value): `dimensions [0 1 -1 0 0 0 0];`
        if first.kind == "LBRACKET":
            dims = self._parse_dimensions()
            # If the next token is `;` or `}`, this is a bare dimensions entry
            if self._peek().kind in {"SEMI", "RBRACE", "EOF"}:
                return Dimensioned(dims=dims, value=Scalar(value=""))
            value = self._parse_atom()
            return Dimensioned(dims=dims, value=value)

        # Named dimensioned (the OpenFOAM idiom in transportProperties):
        #   nu nu [0 2 -1 0 0 0 0] 1e-5
        # the outer key is `nu`, so here we see: WORD [ ... ] value
        if first.kind == "WORD" and self._peek(1).kind == "LBRACKET":
            name = self._advance().text
            dims = self._parse_dimensions()
            value = self._parse_atom()
            return Dimensioned(name=name, dims=dims, value=value)

        # Otherwise it's an atom or a sequence of atoms ("Gauss linear corrected").
        atoms: list[Node] = []
        while self._peek().kind not in {"SEMI", "EOF", "RBRACE"}:
            atoms.append(self._parse_atom())
        if len(atoms) == 1:
            return atoms[0]
        # Collapse multi-word value into an inline list (round-trips correctly).
        return List_(items=atoms, multiline=False)

    def _parse_atom(self) -> Node:
        t = self._peek()
        if t.kind == "LPAREN":
            return self._parse_list_or_vector()
        if t.kind == "NUMBER":
            self._advance()
            txt = t.text
            if any(c in txt for c in ".eE"):
                return Scalar(value=float(txt))
            return Scalar(value=int(txt))
        if t.kind == "STRING":
            self._advance()
            return Scalar(value=t.text)
        if t.kind == "WORD":
            self._advance()
            return Scalar(value=t.text)
        raise SyntaxError(f"Unexpected token {t.kind} ({t.text!r}) at line {t.line}")

    def _parse_dimensions(self) -> tuple:
        self._expect("LBRACKET")
        dims = []
        while self._peek().kind != "RBRACKET":
            t = self._advance()
            if t.kind != "NUMBER":
                raise SyntaxError(f"Expected dim number, got {t.text!r}")
            dims.append(int(float(t.text)))
        self._expect("RBRACKET")
        # OpenFOAM dimensions are 7 numbers; pad if a 5/6-form is used.
        while len(dims) < 7:
            dims.append(0)
        return tuple(dims[:7])

    def _parse_list_or_vector(self) -> Node:
        """Inside `( ... )`. Could be:
              (0 0 -9.81)              → Vector
              (xx xy xz yx yy yz zx zy zz) → Tensor
              ((a b c) (d e f) ...)     → nested List of Vectors
              (word word word)          → List of Scalars
              (inlet { ... } outlet { ... })  → KeyValueList
        """
        self._expect("LPAREN")

        # Try to detect a keyword-list: WORD followed immediately by `{`.
        if self._peek().kind == "WORD" and self._peek(1).kind == "LBRACE":
            return self._parse_kvlist_body()

        items: list[Node] = []
        all_numbers = True
        while self._peek().kind != "RPAREN":
            if self._peek().kind == "EOF":
                raise SyntaxError("Unterminated list")
            atom = self._parse_atom()
            items.append(atom)
            if not (isinstance(atom, Scalar) and isinstance(atom.value, (int, float))):
                all_numbers = False
        self._expect("RPAREN")

        if all_numbers and len(items) == 3:
            return Vector(components=tuple(x.value for x in items))
        if all_numbers and len(items) == 9:
            return Tensor(components=tuple(x.value for x in items))
        # Decide multiline: nested lists → multiline; flat scalars → inline.
        multiline = any(isinstance(it, (List_, Vector, Dict_)) for it in items)
        return List_(items=items, multiline=multiline)

    def _parse_list_or_kvlist(self) -> Node:
        return self._parse_list_or_vector()

    def _parse_kvlist_body(self) -> KeyValueList:
        kv = KeyValueList()
        while self._peek().kind != "RPAREN":
            name = self._advance().text
            self._expect("LBRACE")
            sub = self._parse_dict_body()
            kv.entries.append((name, sub))
        self._expect("RPAREN")
        return kv

    def _consume_semi(self):
        if self._peek().kind == "SEMI":
            self._advance()


# ── Convenience ───────────────────────────────────────────────────────────
def parse_dict(src: str) -> Dict_:
    """Top-level entry: parse OpenFOAM source text → Dict_ root."""
    return FoamParser(src).parse()


def parse_file(path: str) -> Dict_:
    with open(path, "r", encoding="utf-8") as f:
        return parse_dict(f.read())
