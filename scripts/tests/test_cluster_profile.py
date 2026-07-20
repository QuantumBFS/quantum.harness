"""Tests for scripts/cluster_profile.py (TOML profile parsing/validation)."""

import pytest

import cluster_profile as cp

FULL_PROFILE = """\
[identity]
name = "testhpc"

[connection]
repo_path_remote = "/home/u/harness"

[connection.ssh]
alias = "testhpc"

[scheduler]
type = "slurm"

[limits.hard]
max_walltime = "24:00:00"
max_nodes = 4

[limits.soft]
warn_cpus = 64
unusual_partitions = ["gpu-large"]

[limits.paths]
allowed_roots = ["~/scratch", "~/results"]
"""


def _write(tmp_path, text, name="active.toml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# path resolution
# --------------------------------------------------------------------------- #
def test_resolve_explicit_wins(monkeypatch):
    monkeypatch.setenv("HARNESS_PROFILE_FILE", "/env/file.toml")
    assert cp.resolve_profile_path("/explicit.toml") == cp.Path("/explicit.toml")


def test_resolve_env_file(monkeypatch):
    monkeypatch.setenv("HARNESS_PROFILE_FILE", "/env/file.toml")
    assert cp.resolve_profile_path() == cp.Path("/env/file.toml")


def test_resolve_env_named(monkeypatch):
    monkeypatch.delenv("HARNESS_PROFILE_FILE", raising=False)
    monkeypatch.setenv("HARNESS_CLUSTER_PROFILE", "hpc2")
    assert cp.resolve_profile_path().name == "hpc2.toml"


def test_resolve_default(monkeypatch):
    monkeypatch.delenv("HARNESS_PROFILE_FILE", raising=False)
    monkeypatch.delenv("HARNESS_CLUSTER_PROFILE", raising=False)
    assert str(cp.resolve_profile_path()).endswith("active.toml")


# --------------------------------------------------------------------------- #
# load / validate
# --------------------------------------------------------------------------- #
def test_load_valid(tmp_path):
    p = _write(tmp_path, FULL_PROFILE)
    prof = cp.load_profile(p)
    assert prof["identity"]["name"] == "testhpc"


def test_load_missing_raises(tmp_path):
    with pytest.raises(cp.ProfileError, match="not found"):
        cp.load_profile(tmp_path / "nope.toml")


def test_load_malformed_raises(tmp_path):
    p = _write(tmp_path, "this is = = not toml [[[")
    with pytest.raises(cp.ProfileError, match="malformed"):
        cp.load_profile(p)


def test_validate_complete(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    assert cp.validate(prof) == []


def test_validate_missing_sections():
    assert any("connection" in w for w in cp.validate({"identity": {}}))


# --------------------------------------------------------------------------- #
# accessors
# --------------------------------------------------------------------------- #
def test_get_field_nested(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    assert cp.get_field(prof, "scheduler.type") == "slurm"
    # the fields harness_slurm.sh shells out for
    assert cp.get_field(prof, "connection.ssh.alias") == "testhpc"
    assert cp.get_field(prof, "connection.repo_path_remote") == "/home/u/harness"


def test_get_field_missing(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    assert cp.get_field(prof, "scheduler.nope") is None
    assert cp.get_field(prof, "absent.deep.path") is None


def test_get_field_through_nontable(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    # scheduler.type is a string; descending further must yield None
    assert cp.get_field(prof, "scheduler.type.more") is None


def test_get_field_returns_list(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    assert cp.get_field(prof, "limits.soft.unusual_partitions") == ["gpu-large"]


def test_get_limits_full(tmp_path):
    prof = cp.load_profile(_write(tmp_path, FULL_PROFILE))
    lim = cp.get_limits(prof)
    assert lim.hard["max_nodes"] == 4
    assert lim.soft["warn_cpus"] == 64
    assert lim.allowed_roots == ["~/scratch", "~/results"]
    assert lim.configured is True


def test_get_limits_absent():
    lim = cp.get_limits({"identity": {}})
    assert lim.hard == {} and lim.soft == {} and lim.allowed_roots == []
    assert lim.configured is False


def test_get_limits_malformed_types():
    prof = {"limits": "not-a-table"}
    assert cp.get_limits(prof).configured is False
    prof2 = {"limits": {"hard": "x", "soft": 1, "paths": {"allowed_roots": "y"}}}
    lim = cp.get_limits(prof2)
    assert lim.hard == {} and lim.soft == {} and lim.allowed_roots == []


def test_get_partition_by_name():
    profile = {
        "partitions": [
            {"name": "cpu"},
            {"name": "gpu", "required_gres": "gpu:a100:1"},
        ]
    }

    assert cp.get_partition(profile, "gpu") == {
        "name": "gpu",
        "required_gres": "gpu:a100:1",
    }
    assert cp.get_partition(profile, "missing") is None


def test_public_qdeshell_profile_is_safe_and_complete():
    path = cp.Path(__file__).resolve().parents[2] / (
        "skills/using-slurm/profiles/qdeshell.toml"
    )
    profile = cp.load_profile(path)

    assert cp.validate(profile) == []
    assert profile["connection"]["repo_path_remote"] == "~/quantum.harness"
    assert profile["connection"]["ssh"] == {"alias": "qdeshell"}
    assert profile["scheduler"] == {
        "type": "slurm",
        "default_partition": "qdagnormal",
    }

    partition = profile["partitions"][0]
    assert partition["name"] == "qdagnormal"
    assert partition["required_gres"] == "gpu:A800:1"
    assert partition["cores"] == 64
    assert partition["gpu"] == "A800:8"

    limits = cp.get_limits(profile)
    assert limits.hard == {
        "max_walltime": "24:00:00",
        "max_nodes": 1,
        "max_cpus": 64,
        "max_array_size": 200,
    }
    assert limits.soft["warn_walltime"] == "08:00:00"
    assert limits.soft["warn_cpus"] == 16
    assert limits.allowed_roots == ["~/quantum.harness/results", "~/scratch"]
    assert profile["filesystem"] == {
        "home": "~",
        "scratch": "~/scratch",
        "project": "~/quantum.harness",
        "quota": "",
    }
    assert profile["network"] == {
        "internet_from_login": False,
        "internet_from_compute": False,
    }

    forbidden_keys = {
        "host",
        "hostname",
        "user",
        "username",
        "port",
        "key",
        "key_path",
        "identity_file",
        "account",
        "account_name",
    }

    def all_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key.lower()
                yield from all_keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from all_keys(child)

    assert forbidden_keys.isdisjoint(all_keys(profile))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_field_ok(tmp_path, capsys):
    p = _write(tmp_path, FULL_PROFILE)
    rc = cp.main(["--field", "scheduler.type", "--profile", str(p)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "slurm"


def test_cli_field_list(tmp_path, capsys):
    p = _write(tmp_path, FULL_PROFILE)
    cp.main(["--field", "limits.soft.unusual_partitions", "--profile", str(p)])
    assert capsys.readouterr().out.strip() == "gpu-large"


def test_cli_partition_field(tmp_path, capsys):
    profile = FULL_PROFILE + """

[[partitions]]
name = "cpu"

[[partitions]]
name = "gpu"
required_gres = "gpu:a100:1"
"""
    p = _write(tmp_path, profile)
    rc = cp.main(
        [
            "--partition",
            "gpu",
            "--field",
            "required_gres",
            "--profile",
            str(p),
        ]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "gpu:a100:1"


def test_cli_field_bool(tmp_path, capsys):
    p = _write(tmp_path, "[connection]\ninternet = true\n[identity]\n[scheduler]\n")
    cp.main(["--field", "connection.internet", "--profile", str(p)])
    assert capsys.readouterr().out.strip() == "true"


def test_cli_field_missing(tmp_path, capsys):
    p = _write(tmp_path, FULL_PROFILE)
    rc = cp.main(["--field", "nope.field", "--profile", str(p)])
    assert rc == 1
    assert "not set" in capsys.readouterr().err


def test_cli_bad_profile(tmp_path, capsys):
    rc = cp.main(["--field", "x.y", "--profile", str(tmp_path / "absent.toml")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err
