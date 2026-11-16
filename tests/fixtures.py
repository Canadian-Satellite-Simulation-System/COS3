"""COSMOS command definitions captured from the live OpenC3 6.3 plugin (trimmed), for tests."""

IGNORED = ["CCSDS_STREAMID", "CCSDS_SEQUENCE", "CCSDS_LENGTH", "CCSDS_SPARE", "CCSDS_FC", "CCSDS_CHECKSUM"]

HEADER = [
    {"name": "CCSDS_STREAMID", "bit_size": 16, "data_type": "UINT", "default": 6546, "minimum": 0, "maximum": 65535},
    {"name": "CCSDS_FC", "bit_size": 8, "data_type": "UINT", "default": 3, "minimum": 0, "maximum": 255},
]
DERIVED_ITEMS = [{"name": "RECEIVED_COUNT", "bit_size": 0, "data_type": "DERIVED"}]


def packet(target, name, items, **extra):
    return {"target_name": target, "packet_name": name, "description": f"{name} description",
            "items": HEADER + items + DERIVED_ITEMS, **extra}


SET_TORQUE = packet("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_SET_TORQUE_CC", [
    {"name": "WHEEL_NUMBER", "bit_size": 8, "data_type": "UINT", "description": "Wheel number to command",
     "default": 0, "minimum": 0, "maximum": 2, "required": False},
    {"name": "TORQUE", "bit_size": 16, "data_type": "INT", "description": "Torque to set in 10^-4 Newton-meters",
     "default": 0, "minimum": -32768, "maximum": 32767, "required": False},
])

NOOP = packet("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_NOOP_CC", [])

SET_MODE = packet("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC", [
    {"name": "GNC_MODE", "bit_size": 8, "data_type": "UINT", "description": "GN&C Mode", "default": 0,
     "minimum": 0, "maximum": 3, "required": False,
     "states": {"PASSIVE": {"value": 0}, "BDOT_MODE": {"value": 1}, "SUNSAFE_MODE": {"value": 2},
                "INERTIAL_MODE": {"value": 3, "hazardous": "Needs a valid attitude"}}},
])

QUATERNION = packet("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_INERTIAL_QUATERNION_CC", [
    {"name": f"GNC_INER_QUAT{i}", "bit_size": 64, "data_type": "FLOAT", "description": f"Component {i}",
     "default": 1.0 if i == 4 else 0.0, "minimum": -1.0, "maximum": 1.0, "required": False}
    for i in range(1, 5)
])

PROXIMITY = packet("GENERIC_RADIO_DEBUG", "GENERIC_RADIO_PROXIMITY_CC", [
    {"name": "SCID", "bit_size": 16, "data_type": "UINT", "default": 0, "minimum": 0, "maximum": 65535},
    {"name": "PROX_DATA", "bit_size": 512, "data_type": "BLOCK", "description": "Proximity Data",
     "default": {"json_class": "String", "raw": [25, 48, 192, 0, 0, 1, 0, 0]}},
])

CONFIG_ALPHA = packet("SYN_DEBUG", "SYN_CONFIG_ALPHA_CC", [
    {"name": "DEVICE_CONFIG", "bit_size": 32, "data_type": "UINT", "default": 0, "minimum": 0, "maximum": 1,
     "write_conversion": {"class": "OpenC3::GenericConversion", "params": ["(value * 100).to_i\n", None, None, None]}},
])

HAZARDOUS = packet("MGR_DEBUG", "MGR_REBOOT_CC", [], hazardous=True, hazardous_description="Reboots the spacecraft")

REQUIRED = packet("SAMPLE_DEBUG", "SAMPLE_SET_CC", [
    {"name": "VALUE", "bit_size": 8, "data_type": "UINT", "minimum": 0, "maximum": 9, "required": True,
     "units": "V", "units_full": "Volts"},
])

ALL = [SET_TORQUE, NOOP, SET_MODE, QUATERNION, PROXIMITY, CONFIG_ALPHA, HAZARDOUS, REQUIRED]


class FakeClient:
    """Stands in for CosmosJSONAPIClient: serves the fixtures above, counts calls."""

    def __init__(self, packets=ALL):
        self.packets = packets
        self.calls = []

    def get_target(self, target):
        self.calls.append(("get_target", target))
        return {"name": target, "ignored_parameters": IGNORED}

    def get_all_cmds(self, target):
        self.calls.append(("get_all_cmds", target))
        return [p for p in self.packets if p["target_name"] == target]
