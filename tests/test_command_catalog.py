import unittest

from commands.command_catalog import CommandCatalog, UnknownCommand
from commands.targets import CommandPath
from tests.fixtures import FakeClient


class CommandCatalogTest(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.catalog = CommandCatalog(self.client)

    def test_hides_header_and_derived_items(self):
        d = self.catalog.get_command("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_SET_TORQUE_CC")
        self.assertEqual([p.name for p in d.parameters], ["WHEEL_NUMBER", "TORQUE"])
        torque = d.parameters[1]
        self.assertEqual((torque.data_type, torque.bit_size, torque.minimum, torque.maximum), ("INT", 16, -32768, 32767))

    def test_list_commands_for_component_and_path(self):
        names = [c.name for c in self.catalog.list_commands("rw", CommandPath.DEBUG)]
        self.assertEqual(names, ["GENERIC_RW_NOOP_CC", "GENERIC_RW_SET_TORQUE_CC"])

    def test_states_and_hazardous_states(self):
        p = self.catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC").parameters[0]
        self.assertEqual(p.states, {"PASSIVE": 0, "BDOT_MODE": 1, "SUNSAFE_MODE": 2, "INERTIAL_MODE": 3})
        self.assertEqual(p.hazardous_states, ("INERTIAL_MODE",))

    def test_block_default_becomes_hex(self):
        p = self.catalog.get_command("GENERIC_RADIO_DEBUG", "GENERIC_RADIO_PROXIMITY_CC").parameters[1]
        self.assertEqual(p.default, "19 30 C0 00 00 01 00 00")

    def test_write_conversion_note(self):
        p = self.catalog.get_command("SYN_DEBUG", "SYN_CONFIG_ALPHA_CC").parameters[0]
        self.assertEqual(p.conversion, "(value * 100).to_i")

    def test_hazardous_command(self):
        d = self.catalog.get_command("MGR_DEBUG", "MGR_REBOOT_CC")
        self.assertTrue(d.hazardous)
        self.assertEqual(d.hazardous_description, "Reboots the spacecraft")
        self.assertFalse(self.catalog.get_command("GENERIC_RADIO_DEBUG", "GENERIC_RADIO_PROXIMITY_CC").hazardous)

    def test_required_and_full_units(self):
        p = self.catalog.get_command("SAMPLE_DEBUG", "SAMPLE_SET_CC").parameters[0]
        self.assertTrue(p.required)
        self.assertEqual(p.units, "Volts")

    def test_unknown_command(self):
        with self.assertRaises(UnknownCommand):
            self.catalog.get_command("GENERIC_REACTION_WHEEL_DEBUG", "NOPE")

    def test_caches_per_target_until_cleared(self):
        self.catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC")
        self.catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_INERTIAL_QUATERNION_CC")
        self.assertEqual(self.client.calls.count(("get_all_cmds", "GENERIC_ADCS_DEBUG")), 1)
        self.catalog.clear()
        self.catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC")
        self.assertEqual(self.client.calls.count(("get_all_cmds", "GENERIC_ADCS_DEBUG")), 2)

    def test_to_dict_is_json_ready(self):
        import json
        d = self.catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC").to_dict()
        json.dumps(d)
        self.assertEqual(d["parameters"][0]["name"], "GNC_MODE")


if __name__ == "__main__":
    unittest.main()
