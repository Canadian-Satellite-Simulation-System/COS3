import threading
from dataclasses import asdict, dataclass

from commands.targets import CommandPath, targets_for

DERIVED = "DERIVED"


class UnknownCommand(LookupError):
    """No command with that name in the target."""


@dataclass(frozen=True)
class Parameter:
    name: str
    data_type: str  # INT, UINT, FLOAT, STRING, BLOCK
    bit_size: int
    minimum: object = None
    maximum: object = None
    default: object = None
    units: str = None
    description: str = ""
    states: dict = None  # state name -> value, when the parameter is an enumeration
    required: bool = False

    @classmethod
    def from_cosmos(cls, item):
        return cls(
            name=item["name"],
            data_type=item.get("data_type", ""),
            bit_size=item.get("bit_size", 0),
            minimum=item.get("minimum"),
            maximum=item.get("maximum"),
            default=item.get("default"),
            units=item.get("units"),
            description=item.get("description", ""),
            states=_states(item.get("states")),
            required=bool(item.get("required", False)),
        )


@dataclass(frozen=True)
class CommandSummary:
    target: str
    name: str
    description: str
    hazardous: bool


@dataclass(frozen=True)
class CommandDefinition:
    target: str
    name: str
    description: str
    hazardous: bool
    parameters: tuple

    def summary(self):
        return CommandSummary(self.target, self.name, self.description, self.hazardous)

    def to_dict(self):
        return asdict(self)


def _states(states):
    """COSMOS states as {name: value}. Values may come as plain values or {"value": v, ...}."""
    if not states:
        return None

    return {name: (s.get("value") if isinstance(s, dict) else s) for name, s in states.items()}


def _definition(target, packet, ignored):
    return CommandDefinition(
        target=target,
        name=packet["packet_name"],
        description=packet.get("description", ""),
        hazardous=bool(packet.get("hazardous", False)),
        parameters=tuple(
            Parameter.from_cosmos(item)
            for item in packet.get("items", [])
            if item["name"] not in ignored and item.get("data_type") != DERIVED
        ),
    )


class CommandCatalog:
    """Reads and caches command definitions through a CosmosJSONAPIClient."""

    def __init__(self, client):
        self._client = client
        self._cache = {} 
        self._lock = threading.Lock()

    def list_commands(self, component_key, path=CommandPath.DEBUG):
        """Commands for a component, sorted by name. Raises UnknownComponent or CosmosError."""
        commands = []

        for target in targets_for(component_key, path):
            commands.extend(d.summary() for d in self._definitions(target).values())

        return sorted(commands, key=lambda c: (c.target, c.name))

    def get_command(self, target, name):
        """One command with its settable parameters. Raises UnknownCommand or CosmosError."""
        try:
            return self._definitions(target)[name]
        except KeyError:
            raise UnknownCommand(f"{target} {name}") from None

    def clear(self):
        """Forget cached definitions (the COSMOS plugin may have been rebuilt)."""
        with self._lock:
            self._cache.clear()

    def _definitions(self, target):
        with self._lock:
            cached = self._cache.get(target)
        if cached is not None:
            return cached

        ignored = set(self._client.get_target(target).get("ignored_parameters") or [])
        definitions = {
            packet["packet_name"]: _definition(target, packet, ignored)
            for packet in self._client.get_all_cmds(target)
        }
        with self._lock:
            self._cache[target] = definitions
        return definitions
