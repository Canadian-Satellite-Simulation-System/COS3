"""
Checks the parameter values an operator entered for a command.

    values, errors = validate(definition, raw_values)

raw_values maps parameter names to what the form sent (usually strings).
values has the typed values ready for COSMOS's cmd(); errors maps parameter
names to a message for the operator. Send only when errors is empty.

Empty optional fields are left out of values, so COSMOS uses the parameter's
default. BLOCK values are hex (e.g. "0A FF 3C") and come back as bytes.

The browser runs the same checks for instant feedback (ui/assets/command-form.js);
this is the authoritative version.
"""

import math
import re

INTEGER_TYPES = ("INT", "UINT")
HEX_PREFIX = re.compile(r"^0x", re.IGNORECASE)


def validate(definition, raw_values):
    """Returns (values, errors). See the module docstring."""
    raw_values = raw_values or {}
    values, errors = {}, {}
    known = set()

    for p in definition.parameters:
        known.add(p.name)
        raw = raw_values.get(p.name)
        if _blank(raw):
            if p.required:
                errors[p.name] = "Required."
            continue
        try:
            values[p.name] = convert(p, raw)
        except ValueError as err:
            errors[p.name] = str(err)

    for name in raw_values:
        if name not in known:
            errors[name] = "Unknown parameter."

    return values, errors


def convert(p, raw):
    """One parameter's typed value. Raises ValueError with a message for the operator."""
    if p.states:
        return _state_value(p, raw)
    if p.data_type in INTEGER_TYPES:
        return _in_range(p, _integer(raw))
    if p.data_type == "FLOAT":
        return _in_range(p, _float(raw))
    if p.data_type == "BLOCK":
        return _block(p, raw)
    if p.data_type == "STRING":
        return _string(p, raw)
    return raw


def _blank(raw):
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _state_value(p, raw):
    """A state, given by name (any case) or by value."""
    text = str(raw).strip()
    for name, value in p.states.items():
        if text.upper() == name.upper() or text == str(value):
            return value
    raise ValueError(f"Must be one of: {', '.join(p.states)}.")


def _integer(raw):
    if isinstance(raw, bool):
        raise ValueError("Must be a whole number.")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    text = str(raw).strip()
    try:
        return int(text, 16) if HEX_PREFIX.match(text) else int(text, 10)
    except ValueError:
        raise ValueError("Must be a whole number.") from None


def _float(raw):
    if isinstance(raw, bool):
        raise ValueError("Must be a number.")
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise ValueError("Must be a number.") from None
    if not math.isfinite(value):
        raise ValueError("Must be a finite number.")
    return value


def _number(n):
    """A limit as the operator would write it: 1.0 -> "1" (matches the browser's messages)."""
    return str(int(n)) if isinstance(n, float) and n.is_integer() else str(n)


def _range_message(p):
    lo, hi = p.minimum, p.maximum
    if lo is not None and hi is not None:
        return f"Must be between {_number(lo)} and {_number(hi)}."
    return f"Must be at least {_number(lo)}." if lo is not None else f"Must be at most {_number(hi)}."


def _in_range(p, value):
    if (p.minimum is not None and value < p.minimum) or (p.maximum is not None and value > p.maximum):
        raise ValueError(_range_message(p))
    return value


def _max_bytes(p):
    return p.bit_size // 8 if p.bit_size and p.bit_size > 0 else None


def _block(p, raw):
    text = re.sub(r"\s+", "", HEX_PREFIX.sub("", str(raw).strip()))
    try:
        data = bytes.fromhex(text)
    except ValueError:
        raise ValueError("Must be hex bytes, e.g. 0A FF 3C.") from None
    limit = _max_bytes(p)
    if limit is not None and len(data) > limit:
        raise ValueError(f"Must be at most {limit} bytes (got {len(data)}).")
    return data


def _string(p, raw):
    text = str(raw)
    limit = _max_bytes(p)
    if limit is not None and len(text.encode()) > limit:
        raise ValueError(f"Must be at most {limit} bytes.")
    return text
