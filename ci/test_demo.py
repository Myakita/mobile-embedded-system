import unittest

import demo

DEVICES = "List of devices attached\n{}\n\n"


class PickEmulator(unittest.TestCase):
    def test_takes_the_emulator_not_the_phone(self):
        listing = DEVICES.format("R58M12345\tdevice\nemulator-5554\tdevice")
        self.assertEqual(demo.pick_emulator(listing), "emulator-5554")

    def test_never_a_phone(self):
        self.assertIsNone(demo.pick_emulator(DEVICES.format("R58M12345\tdevice")))

    def test_skips_an_emulator_that_is_not_ready(self):
        listing = DEVICES.format("emulator-5554\toffline\nemulator-5556\tunauthorized")
        self.assertIsNone(demo.pick_emulator(listing))


class ChooseEdge(unittest.TestCase):
    def test_order_is_qemu_host_broker(self):
        self.assertEqual(demo.choose_edge(None, True, True), "qemu")
        self.assertEqual(demo.choose_edge(None, False, True), "host")
        self.assertEqual(demo.choose_edge(None, False, False), "broker")

    def test_forced_mode_wins(self):
        self.assertEqual(demo.choose_edge("broker", True, True), "broker")


if __name__ == "__main__":
    unittest.main()
