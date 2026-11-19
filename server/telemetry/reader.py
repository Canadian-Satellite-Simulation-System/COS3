"""Reads component telemetry packets from COSMOS. To add a packet, add it to PACKETS (bottom)."""

from dataclasses import dataclass, field
from typing import Callable, Optional

from server.components import CommandPath, targets_for

# Items COSMOS adds to every packet; not shown as component data
HEADER_ITEMS = {
    "CCSDS_STREAMID", "CCSDS_SEQUENCE", "CCSDS_LENGTH", "CCSDS_SECONDS",
    "CCSDS_SUBSECS", "CCSDS_SPARE", "PACKET_TIMESECONDS", "PACKET_TIMEFORMATTED",
    "RECEIVED_TIMESECONDS", "RECEIVED_TIMEFORMATTED", "RECEIVED_COUNT",
}


class UnknownPacket(LookupError):
    """No packet with that key for the component in PACKETS."""


@dataclass
class Item:
    name: str                                     # COSMOS item name, e.g. RAW_CSS_0
    units: str = ""
    convert: Callable = lambda raw: raw           # Raw value -> displayed value
    level_max: Optional[float] = None             # Set to show a 0-100 % level bar


@dataclass
class Packet:
    name: str                                     # COSMOS packet name
    items: list = field(default_factory=list)     # Empty = show every data item as-is


def scale(factor):
    """Conversion that multiplies the raw value, e.g. counts to volts."""
    return lambda raw: None if raw is None else raw * factor


def level(value, maximum):
    """Percent of the item's range, kept between 0 and 100."""
    if value is None or not maximum:
        return None
    return max(0.0, min(100.0, value / maximum * 100))


def spacecraft_time(seconds, subseconds):
    """CCSDS time: whole seconds + subseconds (1/65536 s)."""
    if seconds is None:
        return None
    return seconds + (subseconds or 0) / 65536


def _round(value, digits):
    """Round numbers for display; leave text, None and other values unchanged."""
    return round(value, digits) if isinstance(value, float) else value


def read_packet(client, component_key, packet_key, path=CommandPath.DEBUG):
    """One packet of a component, in the shape the Telemetry page displays.

    Raises UnknownComponent, UnknownPacket or CosmosError.
    """
    targets = targets_for(component_key, path)
    packet = PACKETS.get(component_key, {}).get(packet_key)
    if packet is None or not targets:
        raise UnknownPacket(f"{component_key} {packet_key}")
    target = targets[0]

    items = client.get_tlm_packet(target, packet.name)  # [[name, value, limit], ...]
    values = {name: value for name, value, _limit in items}
    limits = {name: limit for name, _value, limit in items}

    time_formatted = values.get("PACKET_TIMEFORMATTED")  # "2026/11/11 01:31:55.582"
    time_utc = time_formatted.split(" ")[1] if time_formatted else None

    rows = []
    for item in packet.items or [Item(name) for name in values if name not in HEADER_ITEMS]:
        raw = values.get(item.name)
        value = item.convert(raw)
        rows.append({
            "name": item.name,
            "raw": raw,
            "value": _round(value, 3),
            "level": _round(level(value, item.level_max), 1),
            "units": item.units,
            "limit": limits.get(item.name),
            "time": time_utc,
        })

    return {
        "component": component_key,
        "target": target,
        "packet": packet.name,
        "receivedCount": values.get("RECEIVED_COUNT"),
        "spacecraftTime": _round(spacecraft_time(values.get("CCSDS_SECONDS"), values.get("CCSDS_SUBSECS")), 3),
        "lastUpdate": time_formatted,
        "rows": rows,
        # Every item of the packet as [name, value], like COSMOS Packet Viewer
        "allItems": [[name, value] for name, value, _limit in items],
    }


# Component key -> packet key -> packet
PACKETS = {
    "css": {
        "data": Packet(
            "GENERIC_CSS_DATA_TLM",
            items=[Item(f"RAW_CSS_{i}", units="V", convert=scale(0.001), level_max=5.0) for i in range(6)],
        ),
        # Housekeeping: no items listed, so every data item is passed through as-is
        "hk": Packet("GENERIC_CSS_HK_TLM"),
    },
    # Check the packet name with get_all_tlm_names before relying on it
    "fss": {"data": Packet("GENERIC_FSS_DATA_TLM")},
}
