from pathlib import Path

from oracle.symmetric_oddcycle_cones import (
    exact_chi23_obstruction,
    exact_complementary_sector_audit,
    exact_grade4_formula_replay,
    exact_invariant_chamber_obstruction,
    exact_unit_winding_bernstein_audit,
    exact_unit_winding_endpoint_obstruction,
    load_certificate,
    search_fixed_unit_winding_full_fock_cone,
    search_fixed_unit_winding_pair_cone,
    unit_winding_endpoint_lifts,
    verify_compact_certificate,
)
from oracle.exterior_seed61_short_words import scan_shard


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_symbolic_grade4_positive_cone_and_chi23_obstruction():
    assert exact_grade4_formula_replay()
    assert exact_chi23_obstruction() == {
        "chi2": 13875,
        "chi3": -171633,
        "sum": -157758,
    }


def test_fixed_candidate_compact_cones_replay_exactly():
    expected = {
        "symmetric_oddcycle_grade14_certificate.json": ((1, 4), 10),
        "symmetric_oddcycle_grade24_certificate.json": ((2, 4), 15),
    }
    for name, (grades, dimension) in expected.items():
        result = verify_compact_certificate(load_certificate(FIXTURES / name))
        assert result["status"] == "exact-certificate"
        assert result["grades"] == grades
        assert result["dimension"] == dimension
        assert result["minimum_entry"] >= 0
        assert result["trace_compatible"] is True


def test_fixed_candidate_uses_existing_exact_short_word_oracle():
    result = scan_shard(
        max_depth=4,
        target="symmetric-oddcycle-fixed:0",
    )

    assert result["target"] == "symmetric-oddcycle-fixed:0"
    assert result["dimension"] == 5
    assert result["integer_atom_scale"] == 1
    assert result["status"] == "strictly-positive"
    assert sum(entry["global_word_count"] for entry in result["per_length"]) == 30


def test_complementary_sector_identity_and_local_obstructions_replay_exactly():
    result = exact_complementary_sector_audit()

    assert result["determinant_per_letter"] == 8
    assert all(result["jacobi_checks"].values())
    assert [
        item["sum"] for item in result["negative_complementary_minor_pairs"]
    ] == [-1, -8, -8]
    assert result["mixed_word"] == {
        "word": "0001010101",
        "chi2": -1307360,
        "chi3": 5656076689,
        "determinant": 1073741824,
        "F": 6728511154,
    }
    assert result["grade24_odd135_split_obstruction"] == {
        "word": "101010110111111111111110101010",
        "chi1": -5189582451,
        "chi3": -3485184639156586117103537567,
        "chi5": 1237940039285380274899124224,
        "odd135": -2247244599871205847393995794,
        "even024": 4272808041188297984567253760751379,
        "full_determinant": 4272805793943698113361406366755585,
    }
    assert result["grade14_0235_split_obstruction"] == {
        "word": "101010101111111111111110101010",
        "sector_traces": {
            0: 1,
            1: -4904440699,
            2: 20667680896546356042,
            3: -4380427169319327979657794447,
            4: 4001439983856051764947539321683968,
            5: 1237940039285380274899124224,
        },
        "complement0235": -3142487109366266808212314180,
        "known14": 4001439983856051764947534417243269,
        "full_determinant": 4001436841368942398680726204929089,
    }
    assert result["pure_power_values"] == {
        7: {
            "chi2": 13875,
            "chi3": -171633,
            "determinant": 2097152,
            "F": 1939395,
        },
        10: {
            "chi2": 988330,
            "chi3": -192388191,
            "determinant": 1073741824,
            "F": 882341964,
        },
    }


def test_cycle_invariant_sign_chamber_is_not_sufficient():
    result = exact_invariant_chamber_obstruction()

    assert result["positive_cycle_invariant"] == 8
    assert result["negative_cycle_invariant"] == "-z"
    assert result["coefficients_descending"] == (1, -32, 268, -3000, 8194)
    assert result["F_at_z3"] == 823
    assert result["F_at_z4"] == -1310
    assert result["full_coefficients_descending"] == (1, -32, 396, 3136, 16388)
    assert result["full_at_z3"] == 28577
    assert result["full_at_z4"] == 33476
    assert result["z3_inside_chamber"] is True
    assert result["z4_inside_chamber"] is True


def test_unit_winding_bernstein_coefficients_are_exactly_nonnegative_to_12():
    result = exact_unit_winding_bernstein_audit(max_depth=12)

    assert result["status"] == "all-bernstein-coefficients-nonnegative"
    assert result["interval"] == (0, 1)
    assert result["word_count"] == 8190
    assert result["coefficient_count"] == 98304
    assert result["minimum"] == {"numerator": 17, "denominator": 1}
    assert result["minimum_witness"] == {
        "depth": 1,
        "word": "0",
        "index": 1,
    }


def test_unit_winding_endpoint_lifts_are_four_exact_transpose_paired_atoms():
    atoms = unit_winding_endpoint_lifts()

    assert len(atoms) == 4
    assert all(atom.shape == (22, 22) for atom in atoms)
    assert atoms[1] == atoms[0].T
    assert atoms[3] == atoms[2].T
    assert all(atom.det() != 0 for atom in atoms)


def test_independently_varying_endpoint_cone_has_exact_negative_obstruction():
    result = exact_unit_winding_endpoint_obstruction()

    assert result["status"] == "exact-negative-trace-obstruction"
    assert result["word_length"] == 120
    assert (
        result["word_sha256"]
        == "c09e5facd6b822aad7f43b1fd5c16316a93680a55f129d30c4eb57d0569fa2e6"
    )
    assert result["chi2"] == int(
        "24614177236100370041434232580007283279878745098611151771259234412971687936"
    )
    assert result["chi3"] == -int(
        "20538663057326847435613800827687405586469176053009430459293554608260311687672137729251403596446470745603702784"
    )
    assert result["chi5"] == int(
        "2348542582773833227889480596789337027375682548908319870707290971532209025114608443463698998384768703031934976"
    )
    assert result["F"] == -int(
        "18190120474553014207724320230898068534479316268000740547152031056720819382678784187176552826802467629600079871"
    )


def test_fixed_pair_cone_search_api_stops_on_frozen_mixed_obstruction():
    result = search_fixed_unit_winding_pair_cone(
        attempts=0,
        maxiter=1,
        ray_counts=(22,),
        diagnostic_word_powers=(1, 7),
    )

    assert result["status"] == "exact-negative-trace-obstruction"
    assert result["route"] == "frozen-mixed-word-early-stop"
    assert result["grades"] == (0, 2, 3, 5)
    assert result["endpoint_order"] == ("B1", "B1T")
    assert result["dimension"] == 22
    assert result["atom_count"] == 2
    assert result["diagnostic_pure_word_traces"] == (
        {"word_power": 1, "exact_trace": 17},
        {"word_power": 7, "exact_trace": 1939395},
    )
    assert (
        result["obstruction"]["word"]
        == "101010101111111111111110101010"
    )
    assert result["obstruction"]["complement0235"] == -int(
        "3142487109366266808212314180"
    )


def test_fixed_full_fock_search_api_replays_split_words_without_optimization():
    result = search_fixed_unit_winding_full_fock_cone(
        attempts=0,
        maxiter=1,
        ray_counts=(32,),
    )

    assert result["status"] == "no-exact-certificate-found"
    assert result["route"] == "fixed-full-fock-redundant"
    assert result["grades"] == (0, 1, 2, 3, 4, 5)
    assert result["endpoint_order"] == ("B1", "B1T")
    assert result["dimension"] == 32
    assert result["atom_count"] == 2
    assert result["split_obstruction_full_replays"] == (
        {
            "name": "grade24_odd135_split_obstruction",
            "word": "101010110111111111111110101010",
            "full_determinant": 4272805793943698113361406366755585,
        },
        {
            "name": "grade14_0235_split_obstruction",
            "word": "101010101111111111111110101010",
            "full_determinant": 4001436841368942398680726204929089,
        },
    )
    assert result["redundant"]["status"] == "no-numerical-transform"
