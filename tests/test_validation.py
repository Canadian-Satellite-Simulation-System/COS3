import unittest

from commands.command_catalog import CommandCatalog
from commands.validation import validate
from tests.fixtures import FakeClient


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = CommandCatalog(FakeClient())
        cls.torque = catalog.get_command("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_SET_TORQUE_CC")
        cls.mode = catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_SET_MODE_CC")
        cls.quat = catalog.get_command("GENERIC_ADCS_DEBUG", "GENERIC_ADCS_INERTIAL_QUATERNION_CC")
        cls.prox = catalog.get_command("GENERIC_RADIO_DEBUG", "GENERIC_RADIO_PROXIMITY_CC")
        cls.required = catalog.get_command("SAMPLE_DEBUG", "SAMPLE_SET_CC")
        cls.noop = catalog.get_command("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_NOOP_CC")

    def test_valid_integers(self):
        values, errors = validate(self.torque, {"WHEEL_NUMBER": "2", "TORQUE": "-100"})
        self.assertEqual(errors, {})
        self.assertEqual(values, {"WHEEL_NUMBER": 2, "TORQUE": -100})

    def test_hex_integer(self):
        values, errors = validate(self.torque, {"TORQUE": "0x10"})
        self.assertEqual((values, errors), ({"TORQUE": 16}, {}))

    def test_integer_range_and_type(self):
        _, errors = validate(self.torque, {"WHEEL_NUMBER": "3", "TORQUE": "1.5"})
        self.assertEqual(errors["WHEEL_NUMBER"], "Must be between 0 and 2.")
        self.assertEqual(errors["TORQUE"], "Must be a whole number.")

    def test_empty_optional_uses_cosmos_default(self):
        values, errors = validate(self.torque, {"WHEEL_NUMBER": "", "TORQUE": "  "})
        self.assertEqual((values, errors), ({}, {}))

    def test_required(self):
        _, errors = validate(self.required, {"VALUE": ""})
        self.assertEqual(errors, {"VALUE": "Required."})

    def test_states_by_name_or_value(self):
        self.assertEqual(validate(self.mode, {"GNC_MODE": "bdot_mode"})[0], {"GNC_MODE": 1})
        self.assertEqual(validate(self.mode, {"GNC_MODE": "3"})[0], {"GNC_MODE": 3})
        _, errors = validate(self.mode, {"GNC_MODE": "SPIN"})
        self.assertIn("Must be one of: PASSIVE, BDOT_MODE", errors["GNC_MODE"])

    def test_floats(self):
        values, errors = validate(self.quat, {"GNC_INER_QUAT1": "0.5", "GNC_INER_QUAT2": "-1"})
        self.assertEqual(errors, {})
        self.assertEqual(values, {"GNC_INER_QUAT1": 0.5, "GNC_INER_QUAT2": -1.0})
        _, errors = validate(self.quat, {"GNC_INER_QUAT1": "1.01", "GNC_INER_QUAT2": "abc", "GNC_INER_QUAT3": "nan"})
        self.assertEqual(errors["GNC_INER_QUAT1"], "Must be between -1 and 1.")
        self.assertEqual(errors["GNC_INER_QUAT2"], "Must be a number.")
        self.assertEqual(errors["GNC_INER_QUAT3"], "Must be a finite number.")

    def test_block_hex(self):
        values, errors = validate(self.prox, {"PROX_DATA": "0a ff 3c"})
        self.assertEqual((values["PROX_DATA"], errors), (b"\x0a\xff\x3c", {}))
        _, errors = validate(self.prox, {"PROX_DATA": "0a f"})
        self.assertEqual(errors["PROX_DATA"], "Must be hex bytes, e.g. 0A FF 3C.")
        _, errors = validate(self.prox, {"PROX_DATA": "00" * 65})
        self.assertEqual(errors["PROX_DATA"], "Must be at most 64 bytes (got 65).")

    def test_unknown_parameter(self):
        _, errors = validate(self.noop, {"SURPRISE": "1"})
        self.assertEqual(errors, {"SURPRISE": "Unknown parameter."})

    def test_booleans_are_not_numbers(self):
        _, errors = validate(self.torque, {"TORQUE": True})
        self.assertEqual(errors["TORQUE"], "Must be a whole number.")


if __name__ == "__main__":
    unittest.main()
