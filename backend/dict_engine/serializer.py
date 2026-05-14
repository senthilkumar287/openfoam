"""
OpenFOAM dictionary serializer.

Converts an AST (Dict_) back into native OpenFOAM source text. Always emits
the canonical FoamFile header so output is byte-compatible with stock
OpenFOAM tooling (blockMesh, snappyHexMesh, *Foam solvers).
"""
from __future__ import annotations
from .ast_nodes import Dict_, Scalar


FOAM_BANNER = """\
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM IDE — generated dictionary             |
|  \\\\    /   O peration     |                                                 |
|   \\\\  /    A nd           |                                                 |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
"""

FOAM_FOOTER = (
    "\n// ************************************************************************* //\n"
)


def make_foam_file_header(
    class_name: str,
    object_name: str,
    location: str | None = None,
    foam_format: str = "ascii",
    foam_version: str = "2.0",
) -> Dict_:
    """Construct the standard `FoamFile { ... }` header block as an AST dict.
    Every OpenFOAM dictionary file starts with this."""
    inner = Dict_()
    inner.set("version", foam_version)
    inner.set("format", foam_format)
    inner.set("class", class_name)
    if location:
        inner.set("location", f'"{location}"')
    inner.set("object", object_name)
    header = Dict_()
    header._set_child("FoamFile", inner)
    return header


def serialize(root: Dict_, with_banner: bool = True) -> str:
    """Serialize a root Dict_ to a complete OpenFOAM file string."""
    out = []
    if with_banner:
        out.append(FOAM_BANNER)
    out.append(root.serialize(indent=0))
    out.append(FOAM_FOOTER)
    return "\n".join(out)


def write_dict_file(
    path: str,
    body: Dict_,
    class_name: str,
    object_name: str,
    location: str | None = None,
) -> None:
    """
    Compose `FoamFile` header + body and write to disk.

    `body` is the user's dictionary content (e.g. controlDict entries).
    The header is prepended automatically and is the *only* thing this
    function adds — no other content is injected.
    """
    header = make_foam_file_header(class_name, object_name, location)
    # Merge: header entries first, then a blank line, then body entries.
    merged = Dict_()
    merged.entries.extend(header.entries)
    merged.entries.append(("__blank__", None))
    merged.entries.extend(body.entries)

    text = serialize(merged, with_banner=True)
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
