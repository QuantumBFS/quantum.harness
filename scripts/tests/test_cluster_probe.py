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


# --------------------------------------------------------------------------- #
# Access, per-user caps, node types, whole-node allocation
# --------------------------------------------------------------------------- #
# A synthetic cluster: a shared CPU partition, a group partition reserved for
# account "grpa" on the same mixed hardware, another group's partition, a
# preemptible one, a GPU one, and a request-only gate whose QOS grants 0 cpus.
SINFO9 = """\
shared*|up|1-00:00:00|10|alloc|64|1024000|(null)|old,cpu,img-a
shared*|up|1-00:00:00|4|idle|128|1024000|(null)|new,cpu,img-b
grp|up|7-00:00:00|10|alloc|64|1024000|(null)|old,cpu,img-a
grp|up|7-00:00:00|4|idle|128|1024000|(null)|new,cpu,img-b
other|up|7-00:00:00|14|idle|128|1024000|(null)|new,cpu,img-b
preempt|up|7-00:00:00|14|mix|128|1024000|(null)|new,cpu,img-b
gpu|up|7-00:00:00|3|mix|64|1024000|gpu:a100:4(S:0-1)|gpu,a100
gpu|up|7-00:00:00|2|mix|96|1536000|gpu:h100:8(S:0-1)|gpu,h100
gate|up|infinite|30|mix|128|1024000|(null)|new,cpu,img-b
"""

SCONTROL_PARTS = """\
PartitionName=shared AllowAccounts=ALL AllowQos=normal,short QoS=short OverSubscribe=NO MaxTime=1-00:00:00 DefMemPerCPU=2700 MaxMemPerCPU=2764
PartitionName=grp AllowAccounts=grpa AllowQos=normal,grpa QoS=grpa OverSubscribe=NO MaxTime=7-00:00:00 DefMemPerCPU=UNLIMITED MaxMemPerCPU=UNLIMITED
PartitionName=other AllowAccounts=grpb AllowQos=normal,grpb QoS=grpb OverSubscribe=NO MaxTime=7-00:00:00
PartitionName=preempt AllowAccounts=ALL AllowQos=preempt QoS=N/A OverSubscribe=EXCLUSIVE MaxTime=7-00:00:00
PartitionName=gpu AllowAccounts=ALL AllowQos=normal,gpu QoS=gpu OverSubscribe=NO MaxTime=7-00:00:00
PartitionName=gate AllowAccounts=ALL AllowQos=ALL QoS=gate OverSubscribe=NO MaxTime=UNLIMITED
"""

ASSOC = "grpa||normal,preempt|normal\n"

QOS = """\
normal||||500
short|1-00:00:00|cpu=256,node=4|50|500
grpa|7-00:00:00|cpu=2048,node=16|50|500
grpb|7-00:00:00|cpu=4096,node=32|50|500
gpu|7-00:00:00|cpu=432,gres/gpu=24,mem=6000G|24|500
gate|7-00:00:00|cpu=0,node=0|50|500
"""

TEST_ONLY = """\
@@shared
sbatch: Job 1 to start at 2026-01-01T00:00:00 using 1 processors on nodes n1 in partition shared
@@grp
sbatch: Job 2 to start at 2026-01-01T00:00:00 using 128 processors on nodes n2 in partition grp
@@preempt
sbatch: error: Batch job submission failed: Invalid qos specification
"""

SCONTROL_CFG = "MaxArraySize            = 1001\nMaxMemPerCPU            = 8000\n"


def _rich_runner():
    return FakeRunner(
        {
            "sinfo": SINFO9,
            "scontrol show partition": SCONTROL_PARTS,
            "show assoc": ASSOC,
            "show qos": QOS,
            "--test-only": TEST_ONLY,
            "scontrol show config": SCONTROL_CFG,
            "curl": "200",
        }
    )


def test_parse_partitions_node_types_and_features():
    parts = {p["name"]: p for p in cp.parse_partitions(SINFO9)}
    grp = parts["grp"]
    assert grp["cores"] == 128 and grp["total_nodes"] == 14
    assert [(t["cores"], t["features"], t["nodes"]) for t in grp["node_types"]] == [
        (64, "old,cpu,img-a", 10),
        (128, "new,cpu,img-b", 4),
    ]
    # GPU partition keeps every GPU model as its own node type.
    assert len(parts["gpu"]["node_types"]) == 2
    assert parts["preempt"]["class"] == "preemptible"


def test_parse_partitions_skips_folded_error_text():
    junk = "Command '['ssh', 'sinfo -h -o %P|%a|%l|%D|%t|%c|%m|%G|%f']' timed out\n"
    assert cp.parse_partitions(junk) == []


def test_parse_scontrol_partitions():
    meta = cp.parse_scontrol_partitions(SCONTROL_PARTS)
    assert meta["grp"]["allow_accounts"] == ["grpa"]
    assert meta["grp"]["qos"] == "grpa"
    assert meta["preempt"]["qos"] == ""  # N/A → none
    assert meta["preempt"]["oversubscribe"] == "EXCLUSIVE"
    assert meta["shared"]["def_mem_per_cpu_mb"] == 2700
    assert meta["shared"]["max_mem_per_cpu_mb"] == 2764
    assert meta["grp"]["max_mem_per_cpu_mb"] is None  # UNLIMITED
    assert meta["preempt"]["max_mem_per_cpu_mb"] is None  # absent


def test_probe_reads_mem_per_cpu_partition_first():
    inv = cp.probe(_rich_runner())
    parts = {p["name"]: p for p in inv["partitions"]}
    # Partition value wins; otherwise the cluster-wide MaxMemPerCPU applies.
    assert parts["shared"]["max_mem_per_cpu_mb"] == 2764
    assert parts["shared"]["def_mem_per_cpu_mb"] == 2700
    assert parts["grp"]["max_mem_per_cpu_mb"] == 8000
    assert "def_mem_per_cpu_mb" not in parts["grp"]
    md = cp.build_card_md(inv, "demo")
    assert "Mem/cpu" in md and "2700M/2764M" in md and "—/8000M" in md
    import tomllib

    rows = {p["name"]: p for p in tomllib.loads(cp.build_partitions_toml(inv))["partitions"]}
    assert rows["shared"]["max_mem_per_cpu_mb"] == 2764
    assert rows["grp"]["max_mem_per_cpu_mb"] == 8000


def test_parse_assoc_and_qos():
    assert cp.parse_assoc(ASSOC + "\n|x\n") == [
        {"account": "grpa", "partition": "", "qos": ["normal", "preempt"], "default_qos": "normal"}
    ]
    qos = cp.parse_qos(QOS)
    assert qos["normal"] == {"max_submit": 500}
    assert qos["grpa"] == {
        "max_wall": "7-00:00:00",
        "max_cpus": 2048,
        "max_nodes": 16,
        "max_jobs": 50,
        "max_submit": 500,
    }
    assert qos["gpu"]["max_gpus"] == 24 and "mem" not in qos["gpu"]
    assert cp.parse_tres("(null)") == {}


def test_parse_test_only():
    assert cp.parse_test_only(TEST_ONLY) == {"shared": 1, "grp": 128}


@pytest.mark.parametrize(
    "name,expect",
    [
        ("shared", True),  # AllowAccounts=ALL, qos normal allowed
        ("grp", True),  # own account
        ("other", False),  # someone else's account
        ("preempt", True),  # AllowQos=preempt, user holds preempt
        ("gate", True),  # access rules allow; caps decide later
    ],
)
def test_partition_access(name, expect):
    meta = cp.parse_scontrol_partitions(SCONTROL_PARTS)
    assert cp.partition_access(meta[name], cp.parse_assoc(ASSOC), name) is expect


def test_partition_access_unknown_and_scoped_assoc():
    meta = cp.parse_scontrol_partitions(SCONTROL_PARTS)
    assert cp.partition_access(None, cp.parse_assoc(ASSOC), "x") is None
    assert cp.partition_access(meta["grp"], [], "grp") is None
    scoped = [{"account": "grpa", "partition": "shared", "qos": ["normal"], "default_qos": ""}]
    assert cp.partition_access(meta["grp"], scoped, "grp") is False
    denied = dict(meta["shared"], deny_accounts=["grpa"])
    assert cp.partition_access(denied, cp.parse_assoc(ASSOC), "shared") is False


def test_probe_annotates_access_caps_and_whole_node():
    inv = cp.probe(_rich_runner())
    parts = {p["name"]: p for p in inv["partitions"]}
    assert inv["accounts"] == ["grpa"]
    assert parts["other"]["accessible"] is False
    assert parts["gate"]["accessible"] is False  # QOS grants 0 cpus
    assert parts["grp"]["own_account"] is True and parts["shared"]["own_account"] is False
    assert parts["grp"]["whole_node"] is True  # --test-only got 128 processors
    assert parts["shared"]["whole_node"] is False
    assert parts["preempt"]["whole_node"] is True  # OverSubscribe=EXCLUSIVE
    assert parts["grp"]["user_caps"]["max_cpus"] == 2048  # partition QOS wins
    assert parts["preempt"]["user_caps"] == {"max_submit": 500}  # default QOS only
    # Own-account partition beats the more idle shared one.
    assert inv["default_partition"] == "grp"


def test_probe_dry_runs_only_usable_cpu_partitions():
    runner = _rich_runner()
    cp.probe(runner)
    batch = next(c for c in runner.calls if "--test-only" in c)
    assert "@@grp" in batch and "@@shared" in batch
    assert "@@other" not in batch and "@@gpu" not in batch


def test_probe_raises_on_empty_sinfo():
    with pytest.raises(cp.ProbeError):
        cp.probe(FakeRunner({"sinfo": ""}))


def test_main_reports_probe_error(monkeypatch, capsys):
    monkeypatch.setattr(cp, "detect_login_shell", lambda *a, **k: False)
    monkeypatch.setattr(cp, "SSHRunner", lambda *a, **k: FakeRunner({"sinfo": ""}))
    assert cp.main(["--alias", "hpc"]) == 1
    assert "no partitions" in capsys.readouterr().err


def test_suggest_limits_uses_qos_caps():
    inv = cp.probe(_rich_runner())
    s = inv["suggested_limits"]
    assert s["partition"] == "grp"
    assert s["hard"] == {
        "max_walltime": "7-00:00:00",
        "max_nodes": 16,
        "max_cpus": 2048,
        "max_array_size": 200,
    }
    assert s["soft"]["warn_walltime"] == "08:00:00"
    assert s["soft"]["warn_cpus"] == 128  # one (largest) node
    assert s["soft"]["unusual_partitions"] == ["preempt", "gpu"]
    # The shared partition's QOS is tighter than its MaxTime allows.
    shared = cp.suggest_limits(inv, "shared")["hard"]
    assert shared["max_walltime"] == "1-00:00:00" and shared["max_cpus"] == 256
    assert cp.suggest_limits(inv, "nope") == {}


def test_suggest_limits_without_caps_falls_back_to_partition():
    inv = cp.probe(FakeRunner({"sinfo": SINFO, "curl": "000"}))
    s = cp.suggest_limits(inv, "i64m512u")
    assert s["hard"]["max_nodes"] == 101 and s["hard"]["max_cpus"] == 101 * 64
    assert s["hard"]["max_walltime"] == "7-00:00:00"


def test_secs_to_walltime():
    assert cp.secs_to_walltime(3600) == "01:00:00"
    assert cp.secs_to_walltime(2 * 86400 + 90) == "2-00:01:30"


def test_card_and_toml_show_new_fields():
    inv = cp.probe(_rich_runner())
    md = cp.build_card_md(inv, "demo")
    assert "Whole node" in md and "Per-user caps" in md
    assert "2048 cpu, 16 nodes" in md
    assert "`shared`, `grp`" in md  # identical node sets grouped
    assert "a100, h100" in md  # GPU models, not raw GRES
    assert "Not usable by you (hidden):** 2 partitions (other, gate)" in md
    toml = cp.build_partitions_toml(inv)
    assert 'name = "other"' not in toml and 'name = "gate"' not in toml
    assert "whole_node = true" in toml and 'qos = "grpa"' in toml
    assert "[[partitions.node_types]]" in toml and 'features = ["old", "cpu", "img-a"]' in toml
    assert "[limits.hard]" in toml and "max_cpus = 2048" in toml
    assert 'unusual_partitions = ["preempt", "gpu"]' in toml
    # The emitted TOML parses and round-trips the node types.
    import tomllib

    parsed = tomllib.loads(toml)
    grp = next(p for p in parsed["partitions"] if p["name"] == "grp")
    assert [t["cores"] for t in grp["node_types"]] == [64, 128]
    assert grp["user_caps"]["max_cpus"] == 2048


def test_card_caps_many_node_types():
    types = [
        {"cores": 8 * i, "mem_mb": 1000, "gpu": "", "features": f"f{i}", "nodes": 1}
        for i in range(1, 10)
    ]
    inv = {
        "partitions": [
            {
                "name": "big",
                "class": "default-cpu",
                "cores": 72,
                "mem_mb": 1000,
                "gpu": "",
                "max_wall": "1:00:00",
                "is_default": True,
                "idle_nodes": 0,
                "total_nodes": 9,
                "node_types": types,
            }
        ],
        "limits": {},
        "modules": [],
        "internet_from_login": False,
        "default_partition": "big",
    }
    md = cp.build_card_md(inv, "x")
    assert "+3 more (see `--emit json`)" in md


def test_main_limits_for(monkeypatch, capsys):
    monkeypatch.setattr(cp, "detect_login_shell", lambda *a, **k: False)
    monkeypatch.setattr(cp, "SSHRunner", lambda *a, **k: _rich_runner())
    assert cp.main(["--alias", "hpc", "--emit", "toml", "--limits-for", "shared"]) == 0
    out = capsys.readouterr().out
    assert "per-user caps of 'shared'" in out and 'max_walltime = "1-00:00:00"' in out


def test_main_forced_login_shell(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(cp, "detect_login_shell", lambda *a, **k: 1 / 0)

    def runner(alias, login_shell=True, **k):
        seen["login_shell"] = login_shell
        return _rich_runner()

    monkeypatch.setattr(cp, "SSHRunner", runner)
    assert cp.main(["--alias", "hpc", "--login-shell", "--emit", "card"]) == 0
    assert seen["login_shell"] is True
    capsys.readouterr()
