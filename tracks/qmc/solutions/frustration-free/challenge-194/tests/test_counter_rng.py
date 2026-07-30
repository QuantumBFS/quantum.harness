from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path

import numba
import numpy as np
import pytest

from long_range_percolation.counter_rng import (
    RNG_VERSION,
    STREAM_COUNT,
    StreamIdentity,
    bounded_u32,
    derive_stream_material,
    next_u32,
    philox4x32_10,
    philox4x32_10_reference,
    u32_to_open,
    uniform_open,
)


VECTOR_PATH = Path(__file__).parent / "data" / "random123_philox4x32_10.json"
PHASES = ("validation", "benchmark", "pilot", "confirmatory")


@dataclass(frozen=True)
class Accounting:
    words: int
    blocks: int
    rejections: int


def bounded_u32_from_words_reference(
    bound: int, words: list[int]
) -> tuple[int, Accounting]:
    if not 1 <= bound <= 0xFFFFFFFF:
        raise ValueError("bound must be in [1, 2**32 - 1]")
    threshold = ((1 << 32) - bound) % bound
    consumed = 0
    rejections = 0
    for word in words:
        consumed += 1
        if word < threshold:
            rejections += 1
            continue
        return word % bound, Accounting(
            words=consumed,
            blocks=(consumed + 3) // 4,
            rejections=rejections,
        )
    raise AssertionError("finite word tape exhausted")


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _bounded_u32_from_words_numba(
    bound: np.uint64, words: np.ndarray
) -> tuple[np.uint32, np.ndarray]:
    if bound < np.uint64(1) or bound > np.uint64(0xFFFFFFFF):
        raise ValueError("bound must be in [1, 2**32 - 1]")
    threshold = (np.uint64(1 << 32) - bound) % bound
    consumed = np.uint64(0)
    rejections = np.uint64(0)
    for word in words:
        consumed += np.uint64(1)
        if np.uint64(word) < threshold:
            rejections += np.uint64(1)
            continue
        state = np.array(
            ((consumed + np.uint64(3)) // np.uint64(4), rejections),
            dtype=np.uint64,
        )
        return np.uint32(np.uint64(word) % bound), state
    raise AssertionError("finite word tape exhausted")


def bounded_u32_from_words_compiled(
    bound: int, words: list[int]
) -> tuple[int, Accounting]:
    value, packed = _bounded_u32_from_words_numba(
        np.uint64(bound), np.asarray(words, dtype=np.uint32)
    )
    consumed = next(
        index
        for index in range(1, len(words) + 1)
        if words[index - 1] >= ((1 << 32) - bound) % bound
    )
    return int(value), Accounting(
        words=consumed,
        blocks=int(packed[0]),
        rejections=int(packed[1]),
    )


def _reference_draw(
    counter: np.ndarray,
    key: np.ndarray,
    block: np.ndarray,
    lane_and_valid: np.ndarray,
    accounting: np.ndarray,
) -> int:
    lane = int(lane_and_valid[0])
    valid = int(lane_and_valid[1])
    if not valid:
        block[:] = philox4x32_10_reference(counter, key)
        carry = 1
        for index in range(4):
            if not carry:
                break
            incremented = (int(counter[index]) + carry) & 0xFFFFFFFF
            carry = int(incremented == 0)
            counter[index] = np.uint32(incremented)
        lane = 0
        accounting[1] += np.uint64(1)
    word = int(block[lane])
    lane += 1
    lane_and_valid[0] = np.uint8(0 if lane == 4 else lane)
    lane_and_valid[1] = np.uint8(0 if lane == 4 else 1)
    accounting[0] += np.uint64(1)
    return word


def _reference_bounded(
    bound: int,
    counter: np.ndarray,
    key: np.ndarray,
    block: np.ndarray,
    lane_and_valid: np.ndarray,
    accounting: np.ndarray,
) -> int:
    threshold = ((1 << 32) - bound) % bound
    while True:
        word = _reference_draw(
            counter, key, block, lane_and_valid, accounting
        )
        if word < threshold:
            accounting[2] += np.uint64(1)
            continue
        return word % bound


def _fresh_state(
    counter: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(counter, dtype=np.uint32),
        np.zeros(4, dtype=np.uint32),
        np.zeros(2, dtype=np.uint8),
        np.zeros(3, dtype=np.uint64),
    )


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _compiled_draw_pipeline(
    counter: np.ndarray,
    key: np.ndarray,
    block: np.ndarray,
    lane_and_valid: np.ndarray,
    accounting: np.ndarray,
) -> tuple[np.uint32, float, np.uint32]:
    word = next_u32(counter, key, block, lane_and_valid, accounting)
    uniform = uniform_open(counter, key, block, lane_and_valid, accounting)
    bounded = bounded_u32(
        7, counter, key, block, lane_and_valid, accounting
    )
    return word, uniform, bounded


def test_vector_fixture_is_pinned_to_the_published_random123_source():
    fixture = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    assert fixture["algorithm"] == "Philox4x32-10"
    assert fixture["source"] == (
        "https://github.com/DEShawResearch/random123/blob/main/tests/kat_vectors"
    )
    assert len(fixture["vectors"]) == 2


def test_reference_and_numba_philox_match_published_vectors():
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    for case in vectors["vectors"]:
        counter = np.array(
            [int(item, 16) for item in case["counter"]], dtype=np.uint32
        )
        key = np.array(
            [int(item, 16) for item in case["key"]], dtype=np.uint32
        )
        expected = np.array(
            [int(item, 16) for item in case["output"]], dtype=np.uint32
        )
        np.testing.assert_array_equal(
            philox4x32_10_reference(counter, key), expected
        )
        actual = np.empty(4, dtype=np.uint32)
        philox4x32_10(counter, key, actual)
        np.testing.assert_array_equal(actual, expected)


def test_reference_and_numba_philox_agree_bitwise_beyond_kat_vectors():
    cases = (
        ((1, 2, 3, 4), (5, 6)),
        ((0xFFFFFFFF, 0, 0x80000000, 17), (0xDEADBEEF, 0x12345678)),
        ((0x89ABCDEF, 0x76543210, 0x0F0F0F0F, 0xF0F0F0F0), (11, 13)),
    )
    for counter_words, key_words in cases:
        counter = np.asarray(counter_words, dtype=np.uint32)
        key = np.asarray(key_words, dtype=np.uint32)
        actual = np.empty(4, dtype=np.uint32)
        philox4x32_10(counter, key, actual)
        np.testing.assert_array_equal(
            actual, philox4x32_10_reference(counter, key)
        )
    if not numba.config.DISABLE_JIT:
        assert philox4x32_10.nopython_signatures


def test_reference_philox_is_ordinary_python_and_independent(monkeypatch):
    import long_range_percolation.counter_rng as counter_rng

    assert not isinstance(
        philox4x32_10_reference, numba.core.registry.CPUDispatcher
    )

    def forbidden_compiled_call(*args, **kwargs):
        raise AssertionError("reference called compiled Philox")

    monkeypatch.setattr(
        counter_rng, "philox4x32_10", forbidden_compiled_call
    )
    output = counter_rng.philox4x32_10_reference(
        np.zeros(4, dtype=np.uint32), np.zeros(2, dtype=np.uint32)
    )
    np.testing.assert_array_equal(
        output,
        np.asarray(
            (0x6627E8D5, 0xE169C58D, 0xBC57AC4C, 0x9B00DBD8),
            dtype=np.uint32,
        ),
    )


def test_stream_identity_is_canonical_and_domain_separated():
    base = StreamIdentity(7, "validation", 256, "sigma-1-binary", 3, 0)
    materials = [
        derive_stream_material(replace(base, stream_id=stream))
        for stream in range(STREAM_COUNT)
    ]
    assert len({item.material_sha256 for item in materials}) == STREAM_COUNT
    assert (
        len(
            {
                item.key.tobytes() + item.initial_counter.tobytes()
                for item in materials
            }
        )
        == STREAM_COUNT
    )
    repeated = derive_stream_material(base)
    np.testing.assert_array_equal(repeated.key, materials[0].key)
    np.testing.assert_array_equal(
        repeated.initial_counter, materials[0].initial_counter
    )
    assert repeated.material_sha256 == materials[0].material_sha256
    changed = derive_stream_material(replace(base, phase="benchmark"))
    assert changed.material_sha256 != materials[0].material_sha256


def test_stream_material_matches_exact_canonical_json_and_digest_decoding():
    identity = StreamIdentity(7, "validation", 256, "sigma-1-binary", 3, 0)
    canonical = (
        b'{"length":256,"master_seed":7,"phase":"validation","replica":3,'
        b'"sigma_grid_id":"sigma-1-binary","stream_id":0}'
    )
    digest = hashlib.sha256(
        b"challenge-194-philox-stream-v1\0" + canonical
    ).digest()
    material = derive_stream_material(identity)
    np.testing.assert_array_equal(
        material.key,
        np.frombuffer(digest[0:8], dtype="<u4").astype(np.uint32),
    )
    np.testing.assert_array_equal(
        material.initial_counter,
        np.frombuffer(digest[8:24], dtype="<u4").astype(np.uint32),
    )
    assert material.material_sha256 == digest.hex()
    assert not material.key.flags.writeable
    assert not material.initial_counter.flags.writeable


def test_every_stream_identity_field_is_domain_separated():
    base = StreamIdentity(7, "validation", 256, "sigma-1-binary", 3, 0)
    variants = (
        replace(base, master_seed=8),
        replace(base, phase="benchmark"),
        replace(base, length=258),
        replace(base, sigma_grid_id="sigma-1-decimal"),
        replace(base, replica=4),
        replace(base, stream_id=1),
    )
    hashes = {
        derive_stream_material(identity).material_sha256
        for identity in (base, *variants)
    }
    assert len(hashes) == 1 + len(variants)


def test_stream_derivation_is_independent_of_request_order():
    base = StreamIdentity(7, "validation", 256, "grid", 3, 0)
    forward = {
        stream: derive_stream_material(replace(base, stream_id=stream))
        for stream in range(STREAM_COUNT)
    }
    reverse = {
        stream: derive_stream_material(replace(base, stream_id=stream))
        for stream in reversed(range(STREAM_COUNT))
    }
    assert {
        stream: material.material_sha256
        for stream, material in forward.items()
    } == {
        stream: material.material_sha256
        for stream, material in reverse.items()
    }


@pytest.mark.parametrize("phase", PHASES)
def test_all_frozen_phases_are_accepted(phase: str):
    derive_stream_material(StreamIdentity(0, phase, 2, "grid", 0, 0))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("master_seed", -1),
        ("master_seed", 1 << 64),
        ("master_seed", True),
        ("phase", ""),
        ("phase", "production"),
        ("phase", 1),
        ("length", 0),
        ("length", 3),
        ("length", True),
        ("sigma_grid_id", ""),
        ("sigma_grid_id", " grid"),
        ("sigma_grid_id", "bad\u0000grid"),
        ("sigma_grid_id", "\ud800"),
        ("sigma_grid_id", 1),
        ("replica", -1),
        ("replica", 1 << 64),
        ("replica", False),
        ("stream_id", -1),
        ("stream_id", STREAM_COUNT),
        ("stream_id", True),
    ),
)
def test_stream_identity_rejects_invalid_fields(field: str, value: object):
    identity = StreamIdentity(7, "validation", 256, "grid", 3, 0)
    with pytest.raises(ValueError, match=field):
        derive_stream_material(replace(identity, **{field: value}))


def test_uniform_open_excludes_endpoints_for_extreme_words():
    assert u32_to_open(np.uint32(0)) == 2.0**-33
    assert u32_to_open(np.uint32(0xFFFFFFFF)) == 1.0 - 2.0**-33
    assert RNG_VERSION == "philox4x32-10/open32-v1/bounded-reject-v1"


def test_next_u32_materializes_blocks_in_order_and_counts_exactly():
    key = np.asarray((0x12345678, 0x9ABCDEF0), dtype=np.uint32)
    counter, block, lane_and_valid, accounting = _fresh_state()
    expected_first = philox4x32_10_reference(counter.copy(), key)
    observed = [
        int(next_u32(counter, key, block, lane_and_valid, accounting))
        for _ in range(5)
    ]
    expected_second = philox4x32_10_reference(
        np.asarray((1, 0, 0, 0), dtype=np.uint32), key
    )
    assert observed == [*(int(word) for word in expected_first), int(expected_second[0])]
    np.testing.assert_array_equal(counter, np.asarray((2, 0, 0, 0), np.uint32))
    np.testing.assert_array_equal(lane_and_valid, np.asarray((1, 1), np.uint8))
    np.testing.assert_array_equal(accounting, np.asarray((5, 2, 0), np.uint64))


def test_next_u32_carries_across_little_endian_counter_words():
    key = np.zeros(2, dtype=np.uint32)
    initial = (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    counter, block, lane_and_valid, accounting = _fresh_state(initial)
    expected = philox4x32_10_reference(counter.copy(), key)
    assert int(next_u32(counter, key, block, lane_and_valid, accounting)) == int(
        expected[0]
    )
    np.testing.assert_array_equal(counter, np.asarray((0, 0, 0, 1), np.uint32))
    np.testing.assert_array_equal(accounting, np.asarray((1, 1, 0), np.uint64))


def test_uniform_open_uses_one_word_and_preserves_exact_accounting():
    key = np.zeros(2, dtype=np.uint32)
    counter, block, lane_and_valid, accounting = _fresh_state()
    expected_word = int(philox4x32_10_reference(counter.copy(), key)[0])
    value = uniform_open(counter, key, block, lane_and_valid, accounting)
    assert value == (expected_word + 0.5) * 2.0**-32
    assert 0.0 < value < 1.0
    np.testing.assert_array_equal(accounting, np.asarray((1, 1, 0), np.uint64))


def test_all_draw_primitives_are_callable_from_nopython_code():
    key = np.zeros(2, dtype=np.uint32)
    counter, block, lane_and_valid, accounting = _fresh_state()
    word, uniform, bounded = _compiled_draw_pipeline(
        counter, key, block, lane_and_valid, accounting
    )
    assert int(word) == 0x6627E8D5
    assert 0.0 < uniform < 1.0
    assert 0 <= int(bounded) < 7
    np.testing.assert_array_equal(accounting, np.asarray((3, 1, 0), np.uint64))
    if not numba.config.DISABLE_JIT:
        assert _compiled_draw_pipeline.nopython_signatures


@pytest.mark.parametrize(
    "bound", [1, 3, 7, 2**31 - 1, 2**31, 2**32 - 1]
)
def test_bounded_u32_matches_finite_tape_reference_and_accounts_rejections(
    bound: int,
):
    threshold = ((1 << 32) - bound) % bound
    words = [max(0, threshold - 1), threshold, 0xFFFFFFFF]
    ref_value, ref_state = bounded_u32_from_words_reference(bound, words)
    value, state = bounded_u32_from_words_compiled(bound, words)
    assert value == ref_value
    assert state == ref_state
    assert 0 <= value < bound


@pytest.mark.parametrize(
    "bound", [1, 3, 7, 2**31 - 1, 2**31, 2**32 - 1]
)
def test_production_bounded_u32_matches_ordinary_python_reference(bound: int):
    key = np.asarray((0xDEADBEEF, 0x12345678), dtype=np.uint32)
    ref_counter, ref_block, ref_lane, ref_accounting = _fresh_state()
    actual_counter, actual_block, actual_lane, actual_accounting = _fresh_state()
    expected = _reference_bounded(
        bound, ref_counter, key, ref_block, ref_lane, ref_accounting
    )
    actual = int(
        bounded_u32(
            bound,
            actual_counter,
            key,
            actual_block,
            actual_lane,
            actual_accounting,
        )
    )
    assert actual == expected
    np.testing.assert_array_equal(actual_counter, ref_counter)
    np.testing.assert_array_equal(actual_block, ref_block)
    np.testing.assert_array_equal(actual_lane, ref_lane)
    np.testing.assert_array_equal(actual_accounting, ref_accounting)


def test_finite_tape_adapters_count_rejections_across_block_boundaries():
    bound = 2**31 + 1
    words = [0, 1, 2, 3, 4, 2**31 - 1]
    expected = (2**31 - 1, Accounting(words=6, blocks=2, rejections=5))
    assert bounded_u32_from_words_reference(bound, words) == expected
    assert bounded_u32_from_words_compiled(bound, words) == expected


def test_finite_tape_adapters_fail_closed_when_no_word_is_accepted():
    bound = 2**31 + 1
    words = [0, 1, 2, 3, 4]
    with pytest.raises(AssertionError, match="finite word tape exhausted"):
        bounded_u32_from_words_reference(bound, words)
    with pytest.raises(AssertionError, match="finite word tape exhausted"):
        bounded_u32_from_words_compiled(bound, words)


def test_bounded_u32_matches_ordinary_python_rng_across_multiple_blocks():
    bound = 2**31 + 1
    threshold = ((1 << 32) - bound) % bound
    key = np.asarray((0xA5A5A5A5, 0x01234567), dtype=np.uint32)
    starting_counter = None
    for low_word in range(512):
        first = philox4x32_10_reference(
            np.asarray((low_word, 0, 0, 0), dtype=np.uint32), key
        )
        second = philox4x32_10_reference(
            np.asarray((low_word + 1, 0, 0, 0), dtype=np.uint32), key
        )
        tape = [*(int(word) for word in first), *(int(word) for word in second)]
        accepted_at = next(
            (index for index, word in enumerate(tape) if word >= threshold),
            None,
        )
        if accepted_at is not None and accepted_at >= 4:
            starting_counter = (low_word, 0, 0, 0)
            break
    assert starting_counter is not None

    ref_counter, ref_block, ref_lane, ref_accounting = _fresh_state(
        starting_counter
    )
    actual_counter, actual_block, actual_lane, actual_accounting = _fresh_state(
        starting_counter
    )
    expected = _reference_bounded(
        bound, ref_counter, key, ref_block, ref_lane, ref_accounting
    )
    actual = int(
        bounded_u32(
            bound,
            actual_counter,
            key,
            actual_block,
            actual_lane,
            actual_accounting,
        )
    )
    assert actual == expected
    np.testing.assert_array_equal(actual_counter, ref_counter)
    np.testing.assert_array_equal(actual_block, ref_block)
    np.testing.assert_array_equal(actual_lane, ref_lane)
    np.testing.assert_array_equal(actual_accounting, ref_accounting)
    assert int(actual_accounting[0]) >= 5
    assert int(actual_accounting[1]) >= 2
    assert int(actual_accounting[2]) == int(actual_accounting[0]) - 1


@pytest.mark.parametrize("bound", [0, -1, 2**32, 1.5])
def test_bounded_u32_rejects_invalid_bounds(bound: object):
    key = np.zeros(2, dtype=np.uint32)
    counter, block, lane_and_valid, accounting = _fresh_state()
    with pytest.raises((TypeError, ValueError), match="bound"):
        bounded_u32(
            bound, counter, key, block, lane_and_valid, accounting
        )
