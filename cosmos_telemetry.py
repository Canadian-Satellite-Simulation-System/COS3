"""Read component telemetry from COSMOS 6 through the JSON API.

To add a component: add an entry to COMPONENTS (bottom section). No other code changes.
"""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

COSMOS_URL = os.environ.get("COSMOS_URL", "http://localhost:2900")
COSMOS_PASSWORD = os.environ.get("COSMOS_PASSWORD", "")
COSMOS_SCOPE = "DEFAULT"
LINK = os.environ.get("COSMOS_LINK", "DEBUG")   # Target suffix: DEBUG or RADIO

# Items COSMOS adds to every packet; not shown as component data
HEADER_ITEMS = {
    "CCSDS_STREAMID", "CCSDS_SEQUENCE", "CCSDS_LENGTH", "CCSDS_SECONDS",
    "CCSDS_SUBSECS", "CCSDS_SPARE", "PACKET_TIMESECONDS", "PACKET_TIMEFORMATTED",
    "RECEIVED_TIMESECONDS", "RECEIVED_TIMEFORMATTED", "RECEIVED_COUNT",
}

_token = None


# --- COSMOS connection (generic) ---------------------------------------------

def _post(path, body, headers=None):
    req = urllib.request.Request(
        COSMOS_URL + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode()


def login():
    """COSMOS 5/6 expect {"token": <password>} (renamed to "password" in COSMOS 7)."""
    global _token
    _token = _post("/openc3-api/auth/verify", {"token": COSMOS_PASSWORD}).strip()
    return _token


def call(method, *params):
    """Call one JSON-RPC method. Logs in first, and once more if the token expired."""
    for attempt in range(2):
        if _token is None:
            login()
        body = {"jsonrpc": "2.0", "method": method, "params": list(params),
                "id": 1, "keyword_params": {"scope": COSMOS_SCOPE}}
        try:
            reply = json.loads(_post("/openc3-api/api", body, {"Authorization": _token}))
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                login()
                continue
            raise
        if "error" in reply:
            msg = reply["error"].get("message", "")
            if "Password is invalid" in msg and attempt == 0:
                login()
                continue
            raise RuntimeError(f"COSMOS error in {method}: {msg}")
        return reply["result"]


# --- Component description ---------------------------------------------------------

@dataclass
class Item:
    name: str                                     # COSMOS item name, e.g. RAW_CSS_0
    units: str = ""
    convert: Callable = lambda raw: raw           # Raw value -> displayed value
    level_max: Optional[float] = None             # Set to show a 0-100 % level bar


@dataclass
class Component:
    target: str                                   # Without the _DEBUG/_RADIO suffix
    packet: str
    items: list = field(default_factory=list)     # Empty = show every data item as-is


def scale(factor):
    """Conversion that multiplies the raw value, e.g. counts to volts."""
    return lambda raw: None if raw is None else raw * factor


# --- Generic conversions and packet reading ------------------------------------------

def level(value, maximum):
    """Percent of the item's range, kept between 0 and 100."""
    if value is None or not maximum:
        return None
    return max(0.0, min(100.0, value / maximum * 100))


def spacecraft_time(seconds, subsecs):
    """CCSDS time: whole seconds + subseconds (1/65536 s)."""
    if seconds is None:
        return None
    return seconds + (subsecs or 0) / 65536

def _round(x, digits):
    """Round numbers for display; leave text, None and other values unchanged."""
    return round(x, digits) if isinstance(x, float) else x

def get_component(key):
    """One request to COSMOS for a component, in the shape the Telemetry page displays."""
    comp = COMPONENTS[key]
    target = f"{comp.target}_{LINK}"
    packet = call("get_tlm_packet", target, comp.packet)    # [[name, value, limits], ...]
    v = {name: {"value": value, "limit": limit} for name, value, limit in packet}

    def val(name):
        return v.get(name, {}).get("value")

    time_fmt = val("PACKET_TIMEFORMATTED")                  # "2026/11/11 01:31:55.582"
    time_utc = time_fmt.split(" ")[1] if time_fmt else None

    items = comp.items or [Item(n) for n in v if n not in HEADER_ITEMS]
    rows = []
    for it in items:
        raw = val(it.name)
        value = it.convert(raw)
        lvl = level(value, it.level_max)
        rows.append({
            "name": it.name,
            "raw": raw,
            "value": _round(value, 3),
            "level": _round(lvl, 1),
            "units": it.units,
            "limit": v.get(it.name, {}).get("limit"),
            "time": time_utc,
        })

    sc = spacecraft_time(val("CCSDS_SECONDS"), val("CCSDS_SUBSECS"))
    return {
        "component": key,
        "target": target,
        "packet": comp.packet,
        "received_count": val("RECEIVED_COUNT"),
        "spacecraft_time": _round(sc, 3),
        "last_update": time_fmt,
        "rows": rows,
    }


# --- Components: add new ones here ------------------------------------------------------

COMPONENTS = {
    "css": Component(
        target="GENERIC_CSS",
        packet="GENERIC_CSS_DATA_TLM",
        items=[Item(f"RAW_CSS_{i}", units="V", convert=scale(0.001), level_max=5.0)
               for i in range(6)],
    ),
    # Example: no items listed, so every data item is shown as received.
    # Check the packet name with get_all_tlm_names before relying on it.
    "fss": Component(target="GENERIC_FSS", packet="GENERIC_FSS_DATA_TLM"),
}


if __name__ == "__main__":
    # Terminal test: python3 cosmos_telemetry.py css
    import sys
    print(json.dumps(get_component(sys.argv[1] if len(sys.argv) > 1 else "css"), indent=2))