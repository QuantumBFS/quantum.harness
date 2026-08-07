import unittest

import numpy as np

from borncritical.rng import (
    StreamKey,
    export_rng_state,
    make_rng,
    restore_rng_state,
)


class RngTests(unittest.TestCase):
    def test_same_key_reproduces_stream(self) -> None:
        key = StreamKey(17, "rbim", 12, 3, "disorder")
        left = make_rng(key).normal(size=32)
        right = make_rng(key).normal(size=32)
        np.testing.assert_array_equal(left, right)

    def test_streams_are_order_independent(self) -> None:
        keys = [
            StreamKey(99, "selfdual", 8, replica, "born")
            for replica in range(4)
        ]
        forward = {key: make_rng(key).integers(0, 2**31, size=8) for key in keys}
        reverse = {
            key: make_rng(key).integers(0, 2**31, size=8)
            for key in reversed(keys)
        }
        for key in keys:
            np.testing.assert_array_equal(forward[key], reverse[key])
        self.assertFalse(np.array_equal(forward[keys[0]], forward[keys[1]]))

    def test_state_roundtrip_continues_exactly(self) -> None:
        rng = make_rng(StreamKey(1234, "ising", 16, 0, "test"))
        rng.random(13)
        restored = restore_rng_state(export_rng_state(rng))
        np.testing.assert_array_equal(rng.random(64), restored.random(64))

    def test_fingerprint_is_stable_and_key_sensitive(self) -> None:
        key = StreamKey(7, "rbim", 6, 0, "bonds")
        self.assertEqual(key.fingerprint(), key.fingerprint())
        self.assertNotEqual(
            key.fingerprint(),
            StreamKey(7, "rbim", 6, 1, "bonds").fingerprint(),
        )

    def test_invalid_keys_are_rejected(self) -> None:
        invalid_arguments = [
            (-1, "rbim", 4, 0, "x"),
            (1, "", 4, 0, "x"),
            (1, "rbim", 0, 0, "x"),
            (1, "rbim", 4, -1, "x"),
            (1, "rbim", 4, 0, ""),
        ]
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    StreamKey(*arguments)


if __name__ == "__main__":
    unittest.main()
