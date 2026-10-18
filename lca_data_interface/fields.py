"""Reading one field of a JSON record, named by its call and dotted path when it is absent."""

from __future__ import annotations

from lca_data_interface.errors import MissingField


def field(record: object, path: str, *, call: str) -> object:
    """The value at a dotted `path` of a JSON record, named by its call and path when absent.

    A segment ending in `[]` names a list of records the caller has already descended into, so it
    locates the record in the document and is not walked here.
    """
    value: object = record
    for part in path.split("."):
        if part.endswith("[]"):
            continue
        if not isinstance(value, dict) or part not in value:
            raise MissingField(call, path)
        value = value[part]
    return value
