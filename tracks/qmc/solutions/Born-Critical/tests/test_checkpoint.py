from pathlib import Path
import tempfile
import unittest

import numpy as np

from borncritical.blocking import StreamingBlockAccumulator
from borncritical.checkpoint import load_checkpoint, save_checkpoint
from borncritical.lyapunov import LyapunovQR
from borncritical.rng import StreamKey, make_rng


def advance(
    rng: np.random.Generator,
    blocks: StreamingBlockAccumulator,
    lyapunov: LyapunovQR,
    steps: int,
) -> None:
    for _ in range(steps):
        noise = rng.normal(size=(3, 3))
        lyapunov.push(np.eye(3) + 0.01 * noise)
        blocks.add([float(np.mean(noise)), float(np.std(noise))])


class CheckpointTests(unittest.TestCase):
    def test_interrupted_run_matches_uninterrupted_run(self) -> None:
        key = StreamKey(314159, "checkpoint", 3, 0, "trajectory")

        direct_rng = make_rng(key)
        direct_blocks = StreamingBlockAccumulator(7, 2)
        direct_lyapunov = LyapunovQR(3, 5)
        advance(direct_rng, direct_blocks, direct_lyapunov, 100)

        split_rng = make_rng(key)
        split_blocks = StreamingBlockAccumulator(7, 2)
        split_lyapunov = LyapunovQR(3, 5)
        advance(split_rng, split_blocks, split_lyapunov, 37)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.npz"
            gaussian = np.array(
                [[0.0, 1.0j], [-1.0j, 0.0]], dtype=np.complex128
            )
            save_checkpoint(
                path,
                rng=split_rng,
                blocks=split_blocks,
                lyapunov=split_lyapunov,
                gaussian_state=gaussian,
                extra={"cell_id": "checkpoint-test", "last_block": 5},
            )
            bundle = load_checkpoint(path)
            self.assertEqual(bundle.extra["cell_id"], "checkpoint-test")
            np.testing.assert_array_equal(bundle.gaussian_state, gaussian)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

            advance(bundle.rng, bundle.blocks, bundle.lyapunov, 63)
            np.testing.assert_array_equal(
                direct_blocks.completed_blocks,
                bundle.blocks.completed_blocks,
            )
            np.testing.assert_array_equal(
                direct_blocks.current_sum, bundle.blocks.current_sum
            )
            np.testing.assert_allclose(
                direct_lyapunov.finalize(),
                bundle.lyapunov.finalize(),
                atol=0.0,
                rtol=0.0,
            )
            np.testing.assert_array_equal(
                direct_rng.random(16), bundle.rng.random(16)
            )

    def test_checkpoint_without_gaussian_state_roundtrips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.npz"
            save_checkpoint(
                path,
                rng=make_rng(StreamKey(1, "test", 2, 0, "rng")),
                blocks=StreamingBlockAccumulator(2, 1),
                lyapunov=LyapunovQR(2, 2),
            )
            self.assertIsNone(load_checkpoint(path).gaussian_state)

    def test_missing_checkpoint_arrays_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.npz"
            np.savez(path, metadata=np.array([1], dtype=np.uint8))
            with self.assertRaises(ValueError):
                load_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
