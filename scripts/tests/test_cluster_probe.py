"""Tests for cluster_probe — parsers, emitters, and the injectable probe path.

All ssh/exec goes through a FakeRunner; no test touches a cluster. The sinfo /
scontrol fixtures are real output captured from HKUST-GZ HPC2.
"""

from __future__ import annotations

import cluster_probe as cp
import pytest

# Real captured sinfo -h -o "%P|%a|%l|%D|%t|%c|%m|%G" (subset, multiple states).
SINFO = """\
i64m512u|up|7-00:00:00|20|mix|64|512000|(null)
i64m512u|up|7-00:00:00|29|idle|64|512000|(null)
i64m512u|up|7-00:00:00|52|alloc|64|512000|(null)
i96m3tu|up|7-00:00:00|2|mix|96|3072000|(null)
i96m3tu|up|7-00:00:00|3|idle|96|3072000|(null)
long_cpu|up|14-00:00:00|29|idle|64|512000|(null)
emergency_cpu|up|14-00:00:00|29|idle|64|512000|(null)
i64m1tga800u|up|7-00:00:00|6|mix|64|1024000|gpu:a800:8(S:0)
long_gpu|up|14-00:00:00|9|mix|64|1024000|gpu:a800:8(S:0)
debug|up|30:00|5|idle|64+|512000|(null)
debug|up|30:00|1|mix|64|1024000|gpu:a40:8(S:0)
mohaoran_rent*|up|infinite|1|mix|64|1024000|gpu:a800:8(S:0)
"""

SCONTROL = """\
MaxArraySize            = 10000
DefMemPerCPU            = 4000
MaxMemPerCPU            = 31250
MaxJobCount             = 1000000
SomethingElse           = nope
"""

MODULES = "julia/1.10.9  anaconda3  apptainer-1.4.5  cuda/12.4  gcc-11.1.0  vim  emacs"


class FakeRunner:
    """Maps a substring of the command to canned output (+ optional code)."""

    def __init__(
        self, responses: dict[str, str], code: int = 0, login_shell: bool = True, **_
    ):
        self.responses = responses
        self.code = code
        self.login_shell = login_shell
        self.calls: list[str] = []

    def run(self, cmd: str) -> cp.CmdResult:
        self.calls.append(cmd)
        for key, val in self.responses.items():
            if key in cmd:
                return cp.CmdResult(val, self.code)
        return cp.CmdResult("", 0)


# --------------------------------------------------------------------------- #
# walltime + small helpers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,secs",
    [
        ("7-00:00:00", 7 * 86400),
        ("14-00:00:00", 14 * 86400),
        ("30:00", 30 * 60),
        ("01:02:03", 3723),
        ("infinite", None),
        ("", None),
        ("N/A", None),
    ],
)
def test_parse_walltime(text, secs):
    assert cp.parse_walltime_to_secs(text) == secs


@pytest.mark.parametrize(
    "text,n", [("64", 64), ("64+", 64), ("128", 128), ("", 0), ("x", 0)]
)
def test_int_prefix(text, n):
    assert cp._int_prefix(text) == n


@pytest.mark.parametrize(
    "mb,human", [(512000, "512G"), (1024000, "1T"), (3072000, "3T"), (256000, "256G")]
)
def test_fmt_mem(mb, human):
    assert cp.fmt_mem(mb) == human


@pytest.mark.parametrize(
    "name,mem,gpu,wall,cls",
    [
        ("i64m512u", 512000, "", 7 * 86400, "default-cpu"),
        ("i96m3tu", 3072000, "", 7 * 86400, "high-mem"),
        ("long_cpu", 512000, "", 14 * 86400, "long-cpu"),
        (
            "emergency_cpu",
            512000,
            "",
            14 * 86400,
            "emergency",
        ),  # emergency name takes precedence
        ("emergency_cpu", 512000, "", 7 * 86400, "emergency"),
        ("i64m1tga800u", 1024000, "gpu:a800:8", 7 * 86400, "gpu"),
        ("long_gpu", 1024000, "gpu:a800:8", 14 * 86400, "long-gpu"),
        ("debug", 1024000, "gpu:a40:8", 1800, "debug"),
        ("mohaoran_rent", 1024000, "gpu:a800:8", None, "private"),
        ("slurm01_qos", 1024000, "gpu:a800:8", None, "private"),
    ],
)
def test_classify_partition(name, mem, gpu, wall, cls):
    assert cp.classify_partition(name, mem, gpu, wall) == cls


# --------------------------------------------------------------------------- #
# parse_partitions
# --------------------------------------------------------------------------- #
def test_parse_partitions_aggregates_states():
    parts = {p["name"]: p for p in cp.parse_partitions(SINFO)}
    u = parts["i64m512u"]
    assert u["total_nodes"] == 20 + 29 + 52
    assert u["idle_nodes"] == 29
    assert u["cores"] == 64 and u["mem_mb"] == 512000 and u["gpu"] == ""
    assert u["class"] == "default-cpu"


def test_parse_partitions_gpu_and_default_star():
    parts = {p["name"]: p for p in cp.parse_partitions(SINFO)}
    assert parts["i64m1tga800u"]["gpu"] == "gpu:a800:8(S:0)"
    assert parts["mohaoran_rent"]["is_default"] is True  # trailing * preserved
    assert parts["mohaoran_rent"]["class"] == "private"


def test_parse_partitions_debug_keeps_gpu_across_mixed_rows():
    # debug has a GPU row and a CPU-only row; the GPU spec must survive.
    parts = {p["name"]: p for p in cp.parse_partitions(SINFO)}
    assert parts["debug"]["gpu"] == "gpu:a40:8(S:0)"
    assert parts["debug"]["class"] == "debug"
    assert parts["debug"]["total_nodes"] == 6 and parts["debug"]["idle_nodes"] == 5


def test_parse_partitions_skips_headers_and_short_lines():
    text = "PARTITION|AVAIL|TIMELIMIT|NODES|STATE|CPUS|MEMORY|GRES\n\nbad|row\n" + SINFO
    assert len(cp.parse_partitions(text)) == 8  # same set, junk ignored


# --------------------------------------------------------------------------- #
# scontrol + modules + default pick
# --------------------------------------------------------------------------- #
def test_parse_scontrol_limits():
    lims = cp.parse_scontrol_limits(SCONTROL)
    assert lims == {
        "max_array_size": 10000,
        "def_mem_per_cpu_mb": 4000,
        "max_mem_per_cpu_mb": 31250,
        "max_job_count": 1000000,
    }


def test_parse_scontrol_ignores_nonnumeric_and_unkeyed():
    assert (
        cp.parse_scontrol_limits("Foo = bar\nno-equals-here\nMaxArraySize = NaN") == {}
    )


def test_parse_modules_filters_keys():
    mods = cp.parse_modules(MODULES)
    assert "julia/1.10.9" in mods and "apptainer-1.4.5" in mods and "cuda/12.4" in mods
    assert "vim" not in mods and "emacs" not in mods


def test_pick_default_partition_most_idle():
    parts = cp.parse_partitions(SINFO)
    # i64m512u (29 idle) beats the other default-cpu candidates.
    assert cp.pick_default_partition(parts) == "i64m512u"


def test_pick_default_partition_fallback_and_none():
    assert cp.pick_default_partition([]) is None
    gpu_only = [{"name": "g", "class": "gpu", "idle_nodes": 1, "total_nodes": 1}]
    assert cp.pick_default_partition(gpu_only) is None
    other = [{"name": "x", "class": "high-mem", "idle_nodes": 2, "total_nodes": 2}]
    assert cp.pick_default_partition(other) == "x"


# --------------------------------------------------------------------------- #
# probe() + detect_login_shell via FakeRunner
# --------------------------------------------------------------------------- #
def test_probe_full():
    runner = FakeRunner(
        {
            "sinfo": SINFO,
            "scontrol": SCONTROL,
            "module avail": MODULES,
            "curl": "200",
        }
    )
    inv = cp.probe(runner)
    assert inv["default_partition"] == "i64m512u"
    assert inv["internet_from_login"] is True
    assert inv["limits"]["max_array_size"] == 10000
    assert len(inv["partitions"]) == 8


def test_probe_no_internet():
    runner = FakeRunner(
        {"sinfo": SINFO, "scontrol": "", "module avail": "", "curl": "000"}
    )
    assert cp.probe(runner)["internet_from_login"] is False


def test_detect_login_shell_needed():
    def factory(alias, login_shell=True, timeout=30):
        # plain ssh finds nothing; login shell finds sbatch.
        return FakeRunner(
            {"command -v sbatch": "/opt/slurm/bin/sbatch" if login_shell else ""},
            login_shell=login_shell,
        )

    assert cp.detect_login_shell("hpc", runner_factory=factory) is True


def test_detect_login_shell_not_needed():
    def factory(alias, login_shell=True, timeout=30):
        return FakeRunner(
            {"command -v sbatch": "/usr/bin/sbatch"}, login_shell=login_shell
        )

    assert cp.detect_login_shell("hpc", runner_factory=factory) is False


# --------------------------------------------------------------------------- #
# emitters
# --------------------------------------------------------------------------- #
def test_build_card_md():
    inv = cp.probe(
        FakeRunner(
            {
                "sinfo": SINFO,
                "scontrol": SCONTROL,
                "module avail": MODULES,
                "curl": "200",
            }
        )
    )
    md = cp.build_card_md(inv, "hkust-gz")
    assert md.startswith("# hkust-gz — Cluster Card")
    assert "`i64m512u` *" not in md  # i64m512u is not the starred default
    assert "`mohaoran_rent`" in md and " *" in md  # the starred default shows
    assert "max_array_size=10000" in md
    assert "**Default CPU partition:** `i64m512u`" in md


def test_build_partitions_toml_excludes_private():
    inv = cp.probe(
        FakeRunner(
            {"sinfo": SINFO, "scontrol": SCONTROL, "module avail": "", "curl": "000"}
        )
    )
    toml = cp.build_partitions_toml(inv)
    assert 'name = "i64m512u"' in toml and 'class = "default-cpu"' in toml
    assert "mohaoran_rent" not in toml  # private partitions dropped
    assert "[cluster_limits]" in toml and "max_array_size = 10000" in toml
    assert 'memory = "3T"' in toml  # i96m3tu formatted


def test_build_partitions_toml_no_limits():
    inv = {
        "partitions": [
            {
                "name": "p",
                "class": "default-cpu",
                "cores": 64,
                "mem_mb": 512000,
                "gpu": "",
                "max_wall": "7-00:00:00",
            }
        ],
        "limits": {},
    }
    toml = cp.build_partitions_toml(inv)
    assert "[cluster_limits]" not in toml


# --------------------------------------------------------------------------- #
# SSHRunner + main (impure seams, mocked)
# --------------------------------------------------------------------------- #
def test_sshrunner_wraps_login_shell(monkeypatch):
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args

        class R:
            stdout, stderr, returncode = "ok", "", 0

        return R()

    monkeypatch.setattr(cp.subprocess, "run", fake_run)
    r = cp.SSHRunner("hpc", login_shell=True).run("sinfo")
    assert r.out == "ok" and r.code == 0
    assert seen["args"][-1].startswith("bash -lc ")  # login-shell wrapped
    # plain mode passes the command through unwrapped
    cp.SSHRunner("hpc", login_shell=False).run("sinfo")
    assert seen["args"][-1] == "sinfo"


def test_sshrunner_handles_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ssh")

    monkeypatch.setattr(cp.subprocess, "run", boom)
    r = cp.SSHRunner("hpc").run("sinfo")
    assert r.code == 124 and "no ssh" in r.out


@pytest.mark.parametrize(
    "emit,expect",
    [
        ("json", '"default_partition"'),
        ("toml", "[[partitions]]"),
        ("card", "Cluster Card"),
    ],
)
def test_main_emits(monkeypatch, capsys, emit, expect):
    monkeypatch.setattr(cp, "detect_login_shell", lambda *a, **k: True)
    monkeypatch.setattr(
        cp,
        "SSHRunner",
        lambda *a, **k: FakeRunner(
            {
                "sinfo": SINFO,
                "scontrol": SCONTROL,
                "module avail": MODULES,
                "curl": "200",
            }
        ),
    )
    assert cp.main(["--alias", "hpc", "--emit", emit]) == 0
    assert expect in capsys.readouterr().out


def test_main_no_login_shell(monkeypatch, capsys):
    called = {"detect": False}

    def detect(*a, **k):
        called["detect"] = True
        return True

    monkeypatch.setattr(cp, "detect_login_shell", detect)
    monkeypatch.setattr(
        cp,
        "SSHRunner",
        lambda *a, **k: FakeRunner(
            {"sinfo": SINFO, "scontrol": "", "module avail": "", "curl": "000"}
        ),
    )
    assert cp.main(["--alias", "hpc", "--no-login-shell"]) == 0
    assert called["detect"] is False  # auto-detect skipped
