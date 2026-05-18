use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn bin() -> String {
    if let Ok(path) = std::env::var("CARGO_BIN_EXE_harness-flow") {
        return path;
    }
    let mut path = std::env::current_exe().unwrap();
    path.pop();
    if path.ends_with("deps") {
        path.pop();
    }
    path.push("harness-flow");
    path.to_string_lossy().to_string()
}

fn tmp_dir(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!(
        "harness-flow-{name}-{}-{nanos}",
        std::process::id()
    ));
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn write(path: &Path, content: &str) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).unwrap();
    }
    fs::write(path, content).unwrap();
}

fn run(args: &[&str]) -> std::process::Output {
    Command::new(bin()).args(args).output().unwrap()
}

fn run_with_env(args: &[&str], envs: &[(&str, &str)]) -> std::process::Output {
    let mut command = Command::new(bin());
    command.args(args);
    for (key, value) in envs {
        command.env(key, value);
    }
    command.output().unwrap()
}

fn assert_ok(args: &[&str]) -> String {
    let output = run(args);
    assert!(
        output.status.success(),
        "command failed\nargs: {:?}\nstdout:\n{}\nstderr:\n{}",
        args,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stdout).to_string()
}

fn assert_fail(args: &[&str]) -> String {
    let output = run(args);
    assert!(
        !output.status.success(),
        "command unexpectedly passed\nargs: {:?}\nstdout:\n{}\nstderr:\n{}",
        args,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stderr).to_string()
}

fn assert_fail_with_env(args: &[&str], envs: &[(&str, &str)]) -> String {
    let output = run_with_env(args, envs);
    assert!(
        !output.status.success(),
        "command unexpectedly passed\nargs: {:?}\nstdout:\n{}\nstderr:\n{}",
        args,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stderr).to_string()
}

#[test]
fn init_from_template_and_require_gate() {
    let root = tmp_dir("init");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[flow]
id = "idea_to_verified_plan"

[[gates]]
id = "ideas"

[[gates]]
id = "critic"
requires = ["ideas"]
invalidates = ["revision", "verify"]

[[gates]]
id = "revision"
requires = ["critic"]

[[gates]]
id = "verify"
requires = ["revision"]
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let status = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(status.contains("ideas"));
    assert!(status.contains("pending"));

    let err = assert_fail(&["require", run_dir.to_str().unwrap(), "ideas"]);
    assert!(err.contains("not passed"));
}

#[test]
fn init_copies_external_template_into_run_dir() {
    let root = tmp_dir("init-template-copy");
    let template = root.join("templates").join("custom.toml");
    let run_dir = root.join("run");
    let template_text = r#"
[flow]
id = "copied_template"

[[gates]]
id = "source"

[[gates]]
id = "close"
requires = ["source"]
"#;
    write(&template, template_text);

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let copied = fs::read_to_string(run_dir.join("flow.toml")).unwrap();
    assert_eq!(copied, template_text);
    let status = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(status.contains("copied_template"));
    assert!(status.lines().any(|line| line.starts_with("source\t")));
}

#[test]
fn attempt_finish_passes_with_no_declared_checks() {
    // No protocol.toml = no checks declared = trivial pass.
    let root = tmp_dir("attempt");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "ideas"

[[gates]]
id = "critic"
requires = ["ideas"]
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let attempt = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "ideas",
        "--kind",
        "produce",
        "--actor",
        "agent:main",
    ]);
    let attempt = attempt.trim();
    assert!(attempt.starts_with('a'));

    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt,
    ]);

    assert_ok(&["require", run_dir.to_str().unwrap(), "ideas"]);
    let next = assert_ok(&["next", run_dir.to_str().unwrap()]);
    assert!(next.lines().any(|line| line.trim() == "critic"));
}

#[test]
fn decision_recorded_appears_in_status() {
    let root = tmp_dir("decision");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"plan\"\n");
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&[
        "decide",
        run_dir.to_str().unwrap(),
        "--id",
        "scope",
        "--question",
        "compute scope?",
        "--choice",
        "reduced grid",
        "--reason",
        "compute budget",
    ]);
    let status = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(status.contains("decisions"));
    assert!(status.contains("scope"));
    assert!(status.contains("reduced grid"));
    let state = fs::read_to_string(run_dir.join("progress").join("state.toml")).unwrap();
    assert!(state.contains("scope"));
    assert!(state.contains("reduced grid"));
}

#[test]
fn deviation_recorded_appears_in_status() {
    let root = tmp_dir("deviation");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"plan\"\n");
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&[
        "deviate",
        run_dir.to_str().unwrap(),
        "--id",
        "backend",
        "--statement",
        "MPS instead of TTN",
        "--reason",
        "TTN not wired",
    ]);
    let status = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(status.contains("⚠ deviations"));
    assert!(status.contains("backend"));
    assert!(status.contains("MPS instead of TTN"));
}

#[test]
fn audit_blocks_when_identity_clashes_via_env() {
    // FLOW_ACTOR_ID stamps the same identity on both producer and auditor;
    // identity-clash beats label-distinctness.
    let root = tmp_dir("audit-identity");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"protocol\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "protocol_audit"
kind = "audit"
gate = "protocol"
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let producer = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "protocol",
                "--kind",
                "produce",
                "--actor",
                "agent:label-a",
            ],
            &[("FLOW_ACTOR_ID", "process-7")],
        )
        .stdout,
    )
    .to_string();
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        producer.trim(),
    ]);
    let auditor = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "protocol",
                "--kind",
                "audit",
                "--actor",
                "agent:label-b",
            ],
            &[("FLOW_ACTOR_ID", "process-7")],
        )
        .stdout,
    )
    .to_string();
    let report = run_dir.join("verify").join("r.md");
    write(&report, "audit\n");
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);
    let stdout = String::from_utf8_lossy(&run(&["check", run_dir.to_str().unwrap(), "protocol"]).stdout).to_string();
    assert!(stdout.contains("self-audit: identity"), "stdout: {stdout}");
}

#[test]
fn fresh_invalidates_downstream_when_protocol_changes() {
    // Replaces the old gate_invalidated behavior: a fresh check on the
    // production artifact catches protocol.toml content drift.
    let root = tmp_dir("derived-invalidate");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "protocol"

[[gates]]
id = "production"
requires = ["protocol"]
"#,
    );
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "production_fresh"
kind = "fresh"
gate = "production"
paths = ["cells/cell-0001/manifest.json"]
against = ["protocol.toml"]
"#,
    );
    let cell = run_dir.join("cells/cell-0001/manifest.json");
    write(&cell, "{\"value\": 1}\n");
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    // Pass the protocol gate so production is reachable.
    let protocol_attempt = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "protocol",
        "--kind",
        "produce",
        "--actor",
        "agent:author",
    ]);
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        protocol_attempt.trim(),
    ]);
    // Register the production artifact (snapshots protocol.toml hash).
    assert_ok(&[
        "artifact",
        "add",
        run_dir.to_str().unwrap(),
        "cell1",
        cell.to_str().unwrap(),
        "--kind",
        "manifest",
    ]);
    // Production passes initially.
    let pre = assert_ok(&["check", run_dir.to_str().unwrap(), "production"]);
    assert!(pre.lines().any(|line| line == "status\tpassed"));
    // Mutate the protocol (keeping the same check declared).
    let mut p = fs::read_to_string(&run_dir.join("protocol.toml")).unwrap();
    p.push_str("\n# drifted\n");
    write(&run_dir.join("protocol.toml"), &p);
    // Now production fails — source hash drift.
    let post = run(&["check", run_dir.to_str().unwrap(), "production"]);
    let post_out = String::from_utf8_lossy(&post.stdout).to_string();
    assert!(!post.status.success(), "stdout: {post_out}");
    assert!(post_out.contains("source changed"), "stdout: {post_out}");
}

#[test]
fn held_lock_blocks_second_writer() {
    let root = tmp_dir("lock");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    fs::create_dir(run_dir.join("progress").join(".lock")).unwrap();

    let err = assert_fail_with_env(
        &["status", run_dir.to_str().unwrap()],
        &[("HARNESS_FLOW_LOCK_TIMEOUT_MS", "10")],
    );
    assert!(err.contains("flow lock is held"));
}

#[test]
fn parent_flow_tracks_child_flows_recursively() {
    let root = tmp_dir("campaign");
    let template = root.join("template.toml");
    let parent = root.join("campaign");
    let child = parent.join("runs").join("paper-a");
    write(&template, "[[gates]]\nid = \"closed\"\n");

    assert_ok(&[
        "init",
        parent.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&[
        "init",
        child.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&[
        "attach",
        parent.to_str().unwrap(),
        child.to_str().unwrap(),
        "--as",
        "child",
    ]);

    let status = assert_ok(&["status", parent.to_str().unwrap(), "--recursive"]);
    assert!(status.contains("children"));
    assert!(status.contains("paper-a"));
}

#[test]
fn check_pending_with_no_checks_until_attempt_finishes() {
    // No checks declared + no attempts = pending (nothing demonstrated).
    // After an attempt finishes, the gate passes.
    let root = tmp_dir("check-empty");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    // Before any attempt: pending.
    let pre = run(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(!pre.status.success());
    let pre_out = String::from_utf8_lossy(&pre.stdout).to_string();
    assert!(pre_out.lines().any(|line| line == "status\tpending"));
    // Finish an attempt: passed.
    let attempt = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "source",
        "--kind",
        "produce",
        "--actor",
        "agent:main",
    ]);
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt.trim(),
    ]);
    let post = assert_ok(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(post.lines().any(|line| line == "status\tpassed"));
}

#[test]
fn check_runs_declared_run_kind_and_fails_on_nonzero_exit() {
    let root = tmp_dir("check-run");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "always_fail"
kind = "run"
gate = "source"
cmd = "exit 1"
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let err = assert_fail(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(err.is_empty() || err.contains("status"), "stderr: {err}");
}

#[test]
fn override_records_event_and_satisfies_failing_check() {
    let root = tmp_dir("override");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "always_fail"
kind = "run"
gate = "source"
cmd = "exit 1"
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    // Before override, check fails.
    let pre = run(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(!pre.status.success());

    assert_ok(&[
        "override",
        run_dir.to_str().unwrap(),
        "always_fail",
        "--reason",
        "draft for Slack today",
    ]);

    // After override, check passes.
    let stdout = assert_ok(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(stdout.lines().any(|line| line == "status\tpassed"));
    assert!(stdout.lines().any(|line| line.contains("overridden")));

    // State.toml shows the override.
    let state = fs::read_to_string(run_dir.join("progress").join("state.toml")).unwrap();
    assert!(state.contains("always_fail"));
    assert!(state.contains("draft for Slack today"));
}

#[test]
fn audit_check_rejects_self_verification() {
    let root = tmp_dir("audit-self");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"protocol\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "protocol_audit"
kind = "audit"
gate = "protocol"
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    // Author produces; same actor "verifies" → audit fails.
    let producer = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "protocol",
        "--kind",
        "produce",
        "--actor",
        "agent:author",
    ]);
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        producer.trim(),
    ]);

    let auditor = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "protocol",
        "--kind",
        "audit",
        "--actor",
        "agent:author", // SAME actor — should fail audit
    ]);
    let report = run_dir.join("verify").join("self.md");
    write(&report, "self review\n");
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);

    let status = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(status.lines().any(|line| line.starts_with("protocol\tfailed")));
}

#[test]
fn audit_check_passes_with_distinct_actor() {
    let root = tmp_dir("audit-distinct");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"protocol\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "protocol_audit"
kind = "audit"
gate = "protocol"
"#,
    );

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let producer = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "protocol",
                "--kind",
                "produce",
                "--actor",
                "agent:author",
            ],
            &[("FLOW_ACTOR_ID", "process-author")],
        )
        .stdout,
    )
    .to_string();
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        producer.trim(),
    ]);

    let auditor = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "protocol",
                "--kind",
                "audit",
                "--actor",
                "agent:independent-reviewer",
            ],
            &[("FLOW_ACTOR_ID", "process-reviewer")],
        )
        .stdout,
    )
    .to_string();
    let report = run_dir.join("verify").join("independent.md");
    write(&report, "independent review\n");
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);

    assert_ok(&["require", run_dir.to_str().unwrap(), "protocol"]);
}

fn fresh_setup(name: &str) -> (PathBuf, PathBuf) {
    let root = tmp_dir(name);
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"assembly\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "artifacts_fresh"
kind = "fresh"
gate = "assembly"
paths = ["figs/fig.png"]
against = ["protocol.toml"]
"#,
    );
    let fig = run_dir.join("figs").join("fig.png");
    write(&fig, "fig content v1\n");

    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&[
        "artifact",
        "add",
        run_dir.to_str().unwrap(),
        "fig",
        fig.to_str().unwrap(),
        "--kind",
        "figure",
    ]);
    (run_dir, fig)
}

#[test]
fn fresh_passes_when_artifact_and_sources_unchanged() {
    let (run_dir, _) = fresh_setup("fresh-pass");
    let stdout = assert_ok(&["check", run_dir.to_str().unwrap(), "assembly"]);
    assert!(stdout.lines().any(|line| line == "status\tpassed"));
    assert!(stdout.contains("unchanged"));
}

fn append(path: &Path, more: &str) {
    let mut s = fs::read_to_string(path).unwrap();
    s.push_str(more);
    write(path, &s);
}

#[test]
fn fresh_fails_when_source_content_changes() {
    let (run_dir, _) = fresh_setup("fresh-source-change");
    // Append to protocol.toml without removing the declared check.
    append(&run_dir.join("protocol.toml"), "\n# appended\n");
    let output = run(&["check", run_dir.to_str().unwrap(), "assembly"]);
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    assert!(!output.status.success(), "expected failure; stdout: {stdout}");
    assert!(stdout.contains("source changed"), "stdout: {stdout}");
}

#[test]
fn fresh_fails_when_artifact_content_changes() {
    let (run_dir, fig) = fresh_setup("fresh-artifact-change");
    write(&fig, "fig content v2 (tampered)\n");
    let output = run(&["check", run_dir.to_str().unwrap(), "assembly"]);
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    assert!(!output.status.success(), "expected failure; stdout: {stdout}");
    assert!(stdout.contains("artifact mutated"), "stdout: {stdout}");
}

#[test]
fn fresh_catches_source_change_despite_forward_touch() {
    // The audit loophole: agent mutates a source, then touches the artifact
    // forward to defeat mtime-based freshness. Content-derived fresh ignores
    // mtime; the source hash drift is caught regardless of touch.
    let (run_dir, fig) = fresh_setup("fresh-touch-attack");
    append(&run_dir.join("protocol.toml"), "\n# drifted\n");
    Command::new("touch").arg(&fig).output().unwrap();
    let output = run(&["check", run_dir.to_str().unwrap(), "assembly"]);
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    assert!(!output.status.success(), "expected failure; stdout: {stdout}");
    assert!(stdout.contains("source changed"), "stdout: {stdout}");
}
