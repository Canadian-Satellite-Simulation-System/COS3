"""API responses use camelCase keys; Python fields stay snake_case."""

from dataclasses import fields


def camel_case(name):
    first, *rest = name.split("_")
    return first + "".join(word.capitalize() for word in rest)


def to_json_dict(obj):
    """A dataclass's fields with camelCase keys. Nested dicts (COSMOS state names, parameter values) are left as-is."""
    return {camel_case(f.name): getattr(obj, f.name) for f in fields(obj)}
