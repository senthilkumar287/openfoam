"""
OpenFOAM Dictionary AST — node types.

Every OpenFOAM dictionary is parsed into a tree of these nodes. They are
addressable (path), editable (mutate in place), and serializable back to
byte-identical (or near-identical, modulo whitespace) OpenFOAM syntax.

Design goals:
  * Preserve comments and blank lines (round-trip safe).
  * Distinguish OpenFOAM value kinds: scalar, vector, tensor, list, dict,
    dimensioned, keyword-list, uniform/nonuniform field.
  * No string templating anywhere downstream — callers always operate on nodes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Union


# ── Base ──────────────────────────────────────────────────────────────────
@dataclass
class Node:
    """Base AST node. Subclasses override `serialize()`."""
    # Trivia attached to this node — comments / blank lines that appeared
    # immediately *before* it in the source file. Preserved on write.
    leading_trivia: list[str] = field(default_factory=list)
    trailing_comment: Optional[str] = None  # inline // comment

    def serialize(self, indent: int = 0) -> str:
        raise NotImplementedError


# ── Primitives ────────────────────────────────────────────────────────────
@dataclass
class Scalar(Node):
    """A primitive value: number, string, identifier, bool-like (on/off/yes/no)."""
    value: Union[int, float, str, bool] = 0

    def serialize(self, indent: int = 0) -> str:
        v = self.value
        if isinstance(v, bool):  # OpenFOAM uses on/off, true/false
            return "true" if v else "false"
        if isinstance(v, float):
            # OpenFOAM-style: avoid scientific noise on small ints-as-floats
            if v == int(v) and abs(v) < 1e15:
                return f"{v:g}"
            return repr(v)
        return str(v)


@dataclass
class Vector(Node):
    """A 3-vector (x y z) — e.g. velocity, gravity, point coords."""
    components: tuple = (0.0, 0.0, 0.0)

    def serialize(self, indent: int = 0) -> str:
        return "(" + " ".join(_fmt_num(c) for c in self.components) + ")"


@dataclass
class Tensor(Node):
    """A 9-component tensor (xx xy xz yx yy yz zx zy zz)."""
    components: tuple = (0,) * 9

    def serialize(self, indent: int = 0) -> str:
        return "(" + " ".join(_fmt_num(c) for c in self.components) + ")"


@dataclass
class Dimensioned(Node):
    """A dimensioned value: `nu [0 2 -1 0 0 0 0] 1e-5`."""
    name: Optional[str] = None  # may be None when used inline
    dims: tuple = (0, 0, 0, 0, 0, 0, 0)  # M L T Theta N I lumens
    value: Node = field(default_factory=lambda: Scalar(value=0))

    def serialize(self, indent: int = 0) -> str:
        dims_str = "[" + " ".join(str(d) for d in self.dims) + "]"
        parts = []
        if self.name:
            parts.append(self.name)
        parts.append(dims_str)
        # Empty value is used for bare-dimensions entries (e.g. in 0/U headers).
        val_str = self.value.serialize(indent)
        if val_str != "":
            parts.append(val_str)
        return " ".join(parts)


@dataclass
class FieldValue(Node):
    """`uniform (0 0 0)` or `nonuniform List<vector> ...` — used in 0/ files."""
    kind: str = "uniform"     # "uniform" | "nonuniform"
    value: Node = field(default_factory=lambda: Scalar(value=0))
    list_type: Optional[str] = None  # e.g. "List<vector>" for nonuniform

    def serialize(self, indent: int = 0) -> str:
        if self.kind == "uniform":
            return f"uniform {self.value.serialize(indent)}"
        return f"nonuniform {self.list_type} {self.value.serialize(indent)}"


@dataclass
class List_(Node):
    """An ordered, parenthesized list. Used for vertices, blocks, faces, etc."""
    items: list = field(default_factory=list)
    # If True, serialize one-item-per-line (good for vertices); else inline.
    multiline: bool = True

    def serialize(self, indent: int = 0) -> str:
        # Contract: cursor is at column indent*4. The opening "(" goes there;
        # items go at indent+1; closing ")" goes back at indent.
        pad = "    " * indent
        inner_pad = "    " * (indent + 1)
        if not self.items:
            return "()"
        if self.multiline:
            parts = ["("]
            for item in self.items:
                parts.append(f"{inner_pad}{item.serialize(indent + 1)}")
            parts.append(f"{pad})")
            return "\n".join(parts)
        return "(" + " ".join(it.serialize(indent) for it in self.items) + ")"


@dataclass
class KeyValueList(Node):
    """
    A list-of-(keyword value) pairs, e.g.

        boundary
        (
            inlet { type patch; faces (...); }
            outlet { type patch; faces (...); }
        );

    Each entry has a name and a sub-dictionary or value.
    """
    entries: list = field(default_factory=list)  # list[(name, Node)]

    def serialize(self, indent: int = 0) -> str:
        pad = "    " * indent
        inner_pad = "    " * (indent + 1)
        if not self.entries:
            return "()"
        parts = ["("]
        for name, node in self.entries:
            parts.append(f"{inner_pad}{name}")
            parts.append(f"{inner_pad}{node.serialize(indent + 1)}")
        parts.append(f"{pad})")
        return "\n".join(parts)


# ── Dictionary (the workhorse) ────────────────────────────────────────────
@dataclass
class Dict_(Node):
    """
    An OpenFOAM dictionary block: `key { ... }`  or the root of a file.

    Entries preserve insertion order. Each entry is either:
      - (key, Node)             — `key value;` or `key { ... }`
      - ("__comment__", str)    — a standalone comment line preserved for trivia
      - ("__blank__", None)     — a preserved blank line
    """
    entries: list = field(default_factory=list)

    # ── Mutating API (the dotted-path interface the rest of the app uses) ──
    def set(self, path: str, value: Any) -> None:
        """
        Set a value by dotted path. Creates intermediate dicts as needed.

            controlDict.set("deltaT", 0.001)
            fvSchemes.set("ddtSchemes.default", "Euler")
        """
        keys = path.split(".")
        target = self
        for k in keys[:-1]:
            nxt = target._get_child(k)
            if not isinstance(nxt, Dict_):
                nxt = Dict_()
                target._set_child(k, nxt)
            target = nxt
        target._set_child(keys[-1], _coerce(value))

    def get(self, path: str, default: Any = None) -> Any:
        """Get raw Python value (unwraps Scalar). Returns Node for complex types."""
        keys = path.split(".")
        target = self
        for k in keys:
            if not isinstance(target, Dict_):
                return default
            nxt = target._get_child(k)
            if nxt is None:
                return default
            target = nxt
        if isinstance(target, Scalar):
            return target.value
        return target

    def has(self, path: str) -> bool:
        keys = path.split(".")
        target = self
        for k in keys:
            if not isinstance(target, Dict_):
                return False
            nxt = target._get_child(k)
            if nxt is None:
                return False
            target = nxt
        return True

    def delete(self, path: str) -> bool:
        keys = path.split(".")
        target = self
        for k in keys[:-1]:
            target = target._get_child(k)
            if not isinstance(target, Dict_):
                return False
        last = keys[-1]
        for i, (k, _) in enumerate(target.entries):
            if k == last:
                del target.entries[i]
                return True
        return False

    def keys(self) -> list[str]:
        return [k for k, _ in self.entries if not k.startswith("__")]

    # ── Internal helpers ──────────────────────────────────────────────────
    def _get_child(self, key: str) -> Optional[Node]:
        for k, v in self.entries:
            if k == key:
                return v
        return None

    def _set_child(self, key: str, node: Node) -> None:
        for i, (k, _) in enumerate(self.entries):
            if k == key:
                self.entries[i] = (key, node)
                return
        self.entries.append((key, node))

    # ── Serialization ─────────────────────────────────────────────────────
    # Root vs nested:
    #   - Root dict (indent=0): entries emitted at column 0, no braces.
    #   - Nested dict (indent>0): wrapped in { ... }, body indented.
    def serialize(self, indent: int = 0, _as_root: bool | None = None) -> str:
        """
        Render this dict as OpenFOAM source.
        - If `_as_root` is True (or auto-detected: indent==0 at top-level call),
          emit at column 0 with no braces.
        - Otherwise emit as a `{ ... }` block at the given indent.

        The serializer internals call this with `_as_root=False` for every
        nested dictionary, regardless of indent depth.
        """
        as_root = _as_root if _as_root is not None else (indent == 0)
        if as_root:
            return self._emit_body(indent=indent)
        pad = "    " * indent
        body = self._emit_body(indent=indent + 1)
        return f"{{\n{body}\n{pad}}}"

    def _emit_body(self, indent: int) -> str:
        line_pad = "    " * indent
        parts: list[str] = []
        for key, node in self.entries:
            if key == "__comment__":
                parts.append(f"{line_pad}{node}")
                continue
            if key == "__blank__":
                parts.append("")
                continue
            if key == "__directive__":
                parts.append(f"{line_pad}{node}")
                continue

            if isinstance(node, Dict_):
                # `key\n{\n  ...\n}` — child is always a nested block.
                parts.append(f"{line_pad}{key}")
                parts.append(f"{line_pad}{node.serialize(indent, _as_root=False)}")
            elif isinstance(node, List_) and node.multiline:
                parts.append(f"{line_pad}{key}")
                parts.append(f"{line_pad}{node.serialize(indent)};")
            elif isinstance(node, KeyValueList):
                parts.append(f"{line_pad}{key}")
                parts.append(f"{line_pad}{node.serialize(indent)};")
            else:
                # Inline `key value;`. Pad key to 16 chars for alignment, but
                # always guarantee at least one separating space for long keys.
                ser = node.serialize(indent)
                key_field = f"{key:<16}" if len(key) < 16 else f"{key} "
                parts.append(f"{line_pad}{key_field}{ser};")
        return "\n".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────
def _fmt_num(x):
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return f"{x:g}"
        return repr(x)
    return str(x)


def _coerce(value: Any) -> Node:
    """Convert Python value → Node. Pass-through for existing nodes."""
    if isinstance(value, Node):
        return value
    if isinstance(value, (int, float, str, bool)):
        return Scalar(value=value)
    if isinstance(value, tuple):
        if len(value) == 3:
            return Vector(components=value)
        if len(value) == 9:
            return Tensor(components=value)
        return List_(items=[_coerce(x) for x in value], multiline=False)
    if isinstance(value, list):
        return List_(items=[_coerce(x) for x in value], multiline=True)
    if isinstance(value, dict):
        d = Dict_()
        for k, v in value.items():
            d._set_child(k, _coerce(v))
        return d
    raise TypeError(f"Cannot coerce {type(value).__name__} to AST node")
