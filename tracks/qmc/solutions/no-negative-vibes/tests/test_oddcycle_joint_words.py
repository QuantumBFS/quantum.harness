from oracle.oddcycle_joint_words import (
    exact_rational_word_replay,
    exhaustive_joint_short_words,
    random_joint_long_words,
)


def test_repeated_fixed_point_joint_words_remain_positive():
    points = [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)]
    exhaustive = exhaustive_joint_short_words(points, max_depth=4)
    random = random_joint_long_words(
        points,
        samples=128,
        max_depth=8,
        rng_seed=11,
    )

    assert exhaustive["status"] == "all-tested-words-positive"
    assert exhaustive["alphabet_size"] == 4
    assert exhaustive["word_count"] == 4 + 4**2 + 4**3 + 4**4
    assert random["status"] == "all-tested-words-positive"
    assert random["witness_depth"] <= 8


def test_exhaustive_guard_keeps_failed_or_missing_levels_visible():
    result = exhaustive_joint_short_words(
        [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)],
        max_depth=8,
        max_level_matrices=100,
    )

    assert result["status"] == "resource-limit"
    assert result["max_depth_reached"] == 3
    assert result["next_level_matrices"] == 4**4


def test_depth39_float_negative_replays_as_an_exact_positive_weight():
    word = "201123223230303322300301233223323232302"
    result = exact_rational_word_replay(
        [("0.4", "1", "1"), ("3", "1", "1")],
        word,
    )

    assert result["word_length"] == 39
    assert result["strictly_positive"] is True
    assert result["determinant"]["numerator"] > 0
    assert result["determinant"]["denominator"] > 0
