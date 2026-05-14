"""
OpenFOAM Dictionary Engine — the core of the IDE.

Public API:
    parse_dict(src)             → Dict_
    parse_file(path)            → Dict_
    serialize(root)             → str
    write_dict_file(...)        → None
    make_foam_file_header(...)  → Dict_

The AST node types (Dict_, Scalar, Vector, Tensor, Dimensioned, FieldValue,
List_, KeyValueList) are also exported for typed construction.
"""
from .ast_nodes import (
    Node, Dict_, Scalar, Vector, Tensor, Dimensioned,
    FieldValue, List_, KeyValueList,
)
from .parser import parse_dict, parse_file
from .serializer import serialize, write_dict_file, make_foam_file_header

__all__ = [
    "Node", "Dict_", "Scalar", "Vector", "Tensor", "Dimensioned",
    "FieldValue", "List_", "KeyValueList",
    "parse_dict", "parse_file",
    "serialize", "write_dict_file", "make_foam_file_header",
]
