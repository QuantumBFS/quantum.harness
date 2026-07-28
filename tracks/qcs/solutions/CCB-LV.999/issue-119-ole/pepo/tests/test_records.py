import json

from ole_pepo.records import atomic_write_json, confirmation_token, core_source_digest


def test_atomic_write_json_replaces_complete_document(tmp_path):
    """Breaks if a manifest write leaves JSON missing or only partly written."""
    target = tmp_path / "manifest.json"

    atomic_write_json(target, {"status": "success", "value": 1.0})

    assert json.loads(target.read_text()) == {
        "status": "success",
        "value": 1.0,
    }
    assert not target.with_suffix(".json.tmp").exists()


def test_confirmation_token_is_order_independent():
    """Breaks if equivalent confirmation documents yield different tokens."""
    assert confirmation_token({"a": 1, "b": 2}) == confirmation_token(
        {"b": 2, "a": 1}
    )


def test_core_source_digest_changes_with_core_file(tmp_path):
    """Breaks if the oracle certificate ignores a numerical-core source edit."""
    core = tmp_path / "pepo/src/ole_pepo"
    core.mkdir(parents=True)
    for name in ("qasm.py", "gates.py", "exact.py", "engine.py", "contraction.py"):
        (core / name).write_text(name, encoding="utf-8")
    (tmp_path / "pepo/uv.lock").write_text("lock", encoding="utf-8")

    before = core_source_digest(tmp_path)
    (core / "engine.py").write_text("changed", encoding="utf-8")

    assert core_source_digest(tmp_path) != before
