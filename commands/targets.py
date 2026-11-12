from enum import Enum


class CommandPath(str, Enum):
    """How a command reaches the flight software."""
    DEBUG = "DEBUG"
    RADIO = "RADIO"


class UnknownComponent(KeyError):
    """The component key isn't in COMPONENT_TARGETS."""

# Component key -> COSMOS target base names
COMPONENT_TARGETS = {
    "adcs": ("GENERIC_ADCS",),
    "cam": ("ARDUCAM",),
    "css": ("GENERIC_CSS",),
    "eps": ("GENERIC_EPS",),
    "fss": ("GENERIC_FSS",),
    "gps": ("NOVATEL_OEM615",),
    "imu": ("GENERIC_IMU",),
    "mag": ("GENERIC_MAG",),
    "mgr": ("MGR",),
    "onair": (),
    "radio": ("GENERIC_RADIO",),
    "rw": ("GENERIC_REACTION_WHEEL",),
    "sample": ("SAMPLE",),
    "st": ("GENERIC_STAR_TRACKER",),
    "syn": ("SYN",),
    "thruster": ("GENERIC_THRUSTER",),
    "torquer": ("GENERIC_TORQUER",),
}


def targets_for(component_key, path=CommandPath.DEBUG):
    """COSMOS target names for a component, e.g. ("rw", DEBUG) -> ["GENERIC_REACTION_WHEEL_DEBUG"]."""
    try:
        bases = COMPONENT_TARGETS[component_key]
    except KeyError:
        raise UnknownComponent(component_key) from None

    return [f"{base}_{CommandPath(path).value}" for base in bases]


def component_for(target):
    """The component key that owns a full target name, or None."""
    for path in CommandPath:
        suffix = f"_{path.value}"
        if target.endswith(suffix):
            base = target[: -len(suffix)]
            for key, bases in COMPONENT_TARGETS.items():
                if base in bases:
                    return key
    return None
