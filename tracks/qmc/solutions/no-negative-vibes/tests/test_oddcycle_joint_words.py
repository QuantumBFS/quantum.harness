from oracle.oddcycle_joint_words import (
    exact_rational_word_replay,
    exhaustive_joint_short_words,
    joint_grade34_ratio_profile,
    joint_grade3_frobenius_profile,
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


def test_grade3_profile_keeps_every_joint_word_visible():
    result = joint_grade3_frobenius_profile(
        [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)],
        max_depth=3,
    )

    assert result["status"] == "complete"
    assert result["max_depth_reached"] == 3
    assert [entry["word_count"] for entry in result["per_depth"]] == [
        4,
        16,
        64,
    ]
    assert all(
        entry["maximum_frobenius_ratio_squared"] > 0.0
        for entry in result["per_depth"]
    )


def test_coupled_grade34_profile_uses_the_positive_path_denominator():
    result = joint_grade34_ratio_profile(
        [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)],
        max_depth=3,
    )

    assert result["status"] == "complete"
    assert result["minimum_grade4_entry"] >= 0.0
    assert [entry["word_count"] for entry in result["per_depth"]] == [
        4,
        16,
        64,
    ]
    assert all(
        entry["grade4_path_weight_squared"] > 0.0
        for entry in result["per_depth"]
    )
