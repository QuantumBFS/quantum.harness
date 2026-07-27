"""Tests for scripts/cluster_guardrail.py (resource grading, secrets, paths)."""

import pytest

import cluster_guardrail as g

PROFILE = """\
[identity]
name = "t"
[connection]
[scheduler]
[limits.hard]
max_walltime = "24:00:00"
max_nodes = 4
max_cpus = 256
max_array_size = 200
[limits.soft]
warn_walltime = "08:00:00"
warn_cpus = 64
unusual_partitions = ["gpu-large"]
[limits.paths]
allowed_roots = ["~/scratch", "~/results"]
"""


def _profile(tmp_path, text=PROFILE):
    p = tmp_path / "active.toml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def _script(tmp_path, text):
    p = tmp_path / "job.sh"
    p.write_text(text, encoding="utf-8")
    return str(p)


# --------------------------------------------------------------------------- #
# directive parsing
# --------------------------------------------------------------------------- #
def test_parse_directives_forms():
    text = (
        "#!/bin/bash\n"
        "#SBATCH --time=01:00:00\n"
        "#SBATCH --nodes 2\n"
        "#SBATCH -p debug\n"
        "#SBATCH --array=1-10  # a comment\n"
        "echo first command\n"
        "#SBATCH --time=02:00:00\n"  # ignored after the first command
    )
    d = g.parse_directives(text)
    assert d["time"] == "01:00:00"
    assert d["nodes"] == "2"
    assert d["partition"] == "debug"
    assert d["array"] == "1-10"


def test_parse_directives_empty_and_unknown_short():
    d = g.parse_directives("#SBATCH\n#SBATCH -Z foo\n#SBATCH   \n")
    assert d == {}


@pytest.mark.parametrize(
    "spec,seconds",
    [
        ("30", 1800),
        ("5:00", 300),
        ("01:00:00", 3600),
        ("2-00", 172800),
        ("1-12:00", 129600),
        ("1-00:00:30", 86430),
    ],
)
def test_parse_walltime_ok(spec, seconds):
    assert g.parse_walltime(spec) == seconds


@pytest.mark.parametrize("bad", ["", "1:2:3:4"])
def test_parse_walltime_bad(bad):
    with pytest.raises(ValueError):
        g.parse_walltime(bad)


@pytest.mark.parametrize(
    "spec,count",
    [("1-10", 10), ("0-9", 10), ("1-10:2", 5), ("1,3,5", 3), ("1-3,5,7-9", 7), ("1-200%10", 200)],
)
def test_count_array(spec, count):
    assert g.count_array(spec) == count


def test_count_array_empty_tokens():
    assert g.count_array("1-3,,") == 3


def test_derive_cpus():
    assert g.derive_cpus({"ntasks": "4", "cpus-per-task": "2"}) == 8
    assert g.derive_cpus({"nodes": "2", "ntasks-per-node": "8"}) == 16
    assert g.derive_cpus({}) == 1


# --------------------------------------------------------------------------- #
# secret scan
# --------------------------------------------------------------------------- #
def test_scan_secrets_positive():
    samples = [
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "key=AKIAIOSFODNN7EXAMPLE",
        "token ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "Authorization: Bearer abcdef0123456789abcdef",
        "password = hunter2supersecret",
    ]
    for s in samples:
        assert g.scan_secrets(s), f"expected secret in {s!r}"


def test_scan_secrets_negative():
    benign = "L = 12\nU = 4.0\nfor i in range(100):\n    energy = compute(i)\n"
    assert g.scan_secrets(benign) == []


def test_redact_masks_long_tokens():
    out = g._redact("token = ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert "ghp_abcdefghijklmnop" not in out
    assert "…" in out


# --------------------------------------------------------------------------- #
# build_resources + grade
# --------------------------------------------------------------------------- #
def test_build_resources_warns_on_bad_fields():
    d = {"time": "nonsense", "array": "bad-range-x"}
    res, warns = g.build_resources(d)
    assert res["walltime_seconds"] is None
    assert len(warns) == 2


def _limits(tmp_path):
    import cluster_profile as cp

    return cp.get_limits(cp.load_profile(_profile(tmp_path)))


def test_grade_hard_walltime(tmp_path):
    res, _ = g.build_resources({"time": "48:00:00"})
    verdicts, _ = g.grade(res, _limits(tmp_path))
    assert verdicts[0]["field"] == "walltime" and verdicts[0]["tier"] == "hard"


def test_grade_soft_walltime(tmp_path):
    res, _ = g.build_resources({"time": "10:00:00"})
    verdicts, _ = g.grade(res, _limits(tmp_path))
    assert verdicts[0]["tier"] == "soft"


def test_grade_missing_time_warns(tmp_path):
    res, _ = g.build_resources({"nodes": "1"})
    verdicts, warns = g.grade(res, _limits(tmp_path))
    assert any("max_walltime" in w for w in warns)


def test_grade_nodes_cpus_array_partition(tmp_path):
    lim = _limits(tmp_path)
    res, _ = g.build_resources({"nodes": "8"})
    assert g.grade(res, lim)[0][0]["tier"] == "hard"
    res, _ = g.build_resources({"ntasks": "512", "cpus-per-task": "1"})
    assert g.grade(res, lim)[0][0]["field"] == "cpus"
    res, _ = g.build_resources({"ntasks": "100"})  # > warn_cpus(64), < max(256)
    assert g.grade(res, lim)[0][0]["tier"] == "soft"
    res, _ = g.build_resources({"array": "1-500"})
    assert g.grade(res, lim)[0][0]["field"] == "array_size"
    res, _ = g.build_resources({"partition": "gpu-large"})
    assert g.grade(res, lim)[0][0]["field"] == "partition"


# --------------------------------------------------------------------------- #
# cmd_inspect
# --------------------------------------------------------------------------- #
def test_inspect_clean(tmp_path):
    s = _script(tmp_path, "#SBATCH --time=01:00:00\n#SBATCH --nodes=1\n")
    report, code = g.cmd_inspect(s, _profile(tmp_path))
    assert report["overall"] == "clean" and code == 0


def test_inspect_soft(tmp_path):
    s = _script(tmp_path, "#SBATCH --time=10:00:00\n")
    report, code = g.cmd_inspect(s, _profile(tmp_path))
    assert report["overall"] == "soft" and code == 1


def test_inspect_hard_over_limit(tmp_path):
    s = _script(tmp_path, "#SBATCH --time=48:00:00\n")
    report, code = g.cmd_inspect(s, _profile(tmp_path))
    assert report["overall"] == "hard" and code == 2


def test_inspect_hard_secret(tmp_path):
    s = _script(tmp_path, "#SBATCH --time=01:00:00\nexport KEY=AKIAIOSFODNN7EXAMPLE\n")
    report, code = g.cmd_inspect(s, _profile(tmp_path))
    assert report["secrets"] and report["overall"] == "hard" and code == 2


def test_inspect_no_limits_is_soft(tmp_path):
    prof = _profile(tmp_path, "[identity]\n[connection]\n[scheduler]\n")
    s = _script(tmp_path, "#SBATCH --time=01:00:00\n")
    report, code = g.cmd_inspect(s, prof)
    assert report["overall"] == "soft" and code == 1
    assert any("no [limits]" in w for w in report["warnings"])


def test_inspect_unparseable_field_is_soft(tmp_path):
    # bad --time yields a parse warning → overall soft (fail-closed, not silent)
    s = _script(tmp_path, "#SBATCH --time=garbage\n#SBATCH --nodes=1\n")
    report, code = g.cmd_inspect(s, _profile(tmp_path))
    assert report["overall"] == "soft" and code == 1
    assert any("unparseable" in w for w in report["warnings"])


def test_inspect_bad_profile_is_hard(tmp_path):
    s = _script(tmp_path, "#SBATCH --time=01:00:00\n")
    report, code = g.cmd_inspect(s, str(tmp_path / "absent.toml"))
    assert report["overall"] == "hard" and code == 2


# --------------------------------------------------------------------------- #
# check-path
# --------------------------------------------------------------------------- #
def test_is_under():
    assert g._is_under("~/scratch/run1", "~/scratch")
    assert g._is_under("~/scratch", "~/scratch")
    assert not g._is_under("~/secret", "~/scratch")
    assert not g._is_under("~/scratch/../secret", "~/scratch")


def test_check_path_allowed(tmp_path):
    report, code = g.cmd_check_path("~/scratch/run1", _profile(tmp_path))
    assert report["ok"] is True and code == 0


def test_check_path_outside(tmp_path):
    report, code = g.cmd_check_path("~/elsewhere", _profile(tmp_path))
    assert report["ok"] is False and code == 2


def test_check_path_no_roots(tmp_path):
    prof = _profile(tmp_path, "[identity]\n[connection]\n[scheduler]\n")
    report, code = g.cmd_check_path("~/scratch/x", prof)
    assert code == 2 and "no allowed_roots" in report["message"]


def test_check_path_bad_profile(tmp_path):
    report, code = g.cmd_check_path("~/scratch/x", str(tmp_path / "absent.toml"))
    assert code == 2 and report["ok"] is False


# --------------------------------------------------------------------------- #
# main dispatch
# --------------------------------------------------------------------------- #
def test_main_inspect(tmp_path, capsys):
    s = _script(tmp_path, "#SBATCH --time=01:00:00\n")
    rc = g.main(["inspect", s, "--profile", _profile(tmp_path)])
    assert rc == 0
    assert '"overall": "clean"' in capsys.readouterr().out


def test_main_check_path(tmp_path, capsys):
    rc = g.main(["check-path", "~/scratch/x", "--profile", _profile(tmp_path)])
    assert rc == 0
    capsys.readouterr()


def test_cli_directive_field(tmp_path, capsys):
    script = _script(
        tmp_path,
        "#SBATCH --partition=script-gpu\n#SBATCH --gres=gpu:script:4\n",
    )

    rc = g.main(["directive", script, "--field", "gres"])

    assert rc == 0
    assert capsys.readouterr().out.strip() == "gpu:script:4"
