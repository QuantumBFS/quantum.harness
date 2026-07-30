import os

from oracle.oddcycle_final_certificate import final_certificate_summary
from oracle.oddcycle_final_certificate import _source_commit


def test_final_certificate_replays_every_exact_publication_gate():
    result = final_certificate_summary()

    assert result["status"] == "all-exact-gates-passed"
    assert result["candidate"]["dimension"] == 5
    assert result["candidate"]["points"] == [
        ["1/1000", "1", "1"],
        ["4/5", "1", "1"],
    ]
    assert result["gates"] == {
        "arbitrary_word_determinant_positive": True,
        "no_common_strict_quadratic_metric": True,
        "hermitian_interacting_positive_field_model": True,
        "outside_wei_majorana_sufficient_class": True,
    }
    assert result["majorana_wei"] == {
        "commutant_nullity": 1,
        "boundary_sign": 1,
        "wei_sign": -1,
    }
    assert len(result["exact_certificate_sha256"]) == 64
    assert result["discovery_evidence"][
        "exhaustive_words_through_depth_12"
    ] == 22_369_620
    assert result["physical"]["field_coefficients"] == (
        "37/41",
        "1/41",
        "1/41",
        "1/41",
        "1/41",
    )


def test_source_commit_waits_for_a_cold_git_index(tmp_path, monkeypatch):
    expected_commit = "0123456789abcdef0123456789abcdef01234567"
    fake_git = tmp_path / "git"
    fake_git.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "rev-parse" ]; then\n'
        f"  echo {expected_commit}\n"
        "else\n"
        "  sleep 6\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    monkeypatch.setenv(
        "PATH",
        f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
    )

    assert _source_commit() == expected_commit
