use sha2::{Digest, Sha256};
use std::fs;
use std::io::Read;
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

fn file_hash(path: &Path) -> String {
    let mut file = fs::File::open(path).unwrap();
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 8192];
    loop {
        let n = file.read(&mut buf).unwrap();
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    format!("sha256:{:x}", hasher.finalize())
}

fn write_audit(report: &Path, status: &str) {
    write(report, "audit findings\n");
    write(
        &report.with_extension("toml"),
        &format!("status = \"{status}\"\n"),
    );
}

fn run(args: &[&str]) -> std::process::Output {
    let mut command = Command::new(bin());
    command.args(args);
    command.env_remove("CODEX_THREAD_ID");
    command.env_remove("CLAUDE_SESSION_ID");
    command.output().unwrap()
}

fn run_with_env(args: &[&str], envs: &[(&str, &str)]) -> std::process::Output {
    let mut command = Command::new(bin());
    command.args(args);
    command.env_remove("CODEX_THREAD_ID");
    command.env_remove("CLAUDE_SESSION_ID");
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

    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
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
    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
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
        "run",
        "--actor",
        "agent:main",
    ]);
    let attempt = attempt.trim();
    assert!(attempt.starts_with('a'));

    assert_ok(&["attempt", "finish", run_dir.to_str().unwrap(), attempt]);

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
    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
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
    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
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
                "run",
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
    write_audit(&report, "pass");
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);
    let stdout =
        String::from_utf8_lossy(&run(&["check", run_dir.to_str().unwrap(), "protocol"]).stdout)
            .to_string();
    assert!(stdout.contains("self-audit: identity"), "stdout: {stdout}");
}

#[test]
fn audit_identity_prefers_host_session() {
    let root = tmp_dir("audit-host-session");
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
                "run",
                "--actor",
                "agent:author",
            ],
            &[
                ("CODEX_THREAD_ID", "same-session"),
                ("FLOW_ACTOR_ID", "author"),
            ],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            producer.trim(),
        ],
        &[
            ("CODEX_THREAD_ID", "same-session"),
            ("FLOW_ACTOR_ID", "author"),
        ],
    );
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
                "agent:auditor",
            ],
            &[
                ("CODEX_THREAD_ID", "same-session"),
                ("FLOW_ACTOR_ID", "auditor"),
            ],
        )
        .stdout,
    )
    .to_string();
    let report = run_dir.join("verify").join("audit.md");
    write_audit(&report, "pass");
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            auditor.trim(),
            "--report",
            report.to_str().unwrap(),
        ],
        &[
            ("CODEX_THREAD_ID", "same-session"),
            ("FLOW_ACTOR_ID", "auditor"),
        ],
    );
    let stdout =
        String::from_utf8_lossy(&run(&["check", run_dir.to_str().unwrap(), "protocol"]).stdout)
            .to_string();
    assert!(
        stdout.contains("self-audit: identity codex:same-session"),
        "stdout: {stdout}"
    );
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
        "run",
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
        "run",
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
        "run",
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
    write_audit(&report, "pass");
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);

    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
    assert!(status
        .lines()
        .any(|line| line.starts_with("protocol\tfailed")));
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
                "run",
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
    write_audit(&report, "pass");
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

#[test]
fn audit_finish_requires_typed_sidecar() {
    let root = tmp_dir("audit-sidecar-missing");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"protocol\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "audit"
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
    let producer = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "protocol",
        "--kind",
        "run",
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
        "agent:auditor",
    ]);
    let report = run_dir.join("verify").join("audit.md");
    write(&report, "audit findings\n");
    let err = assert_fail(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        auditor.trim(),
        "--report",
        report.to_str().unwrap(),
    ]);
    assert!(err.contains("typed sidecar"), "stderr: {err}");
}

#[test]
fn audit_sidecar_warn_blocks_gate() {
    let root = tmp_dir("audit-sidecar-warn");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"protocol\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "audit"
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
                "run",
                "--actor",
                "agent:author",
            ],
            &[("FLOW_ACTOR_ID", "author")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            producer.trim(),
        ],
        &[("FLOW_ACTOR_ID", "author")],
    );
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
                "agent:auditor",
            ],
            &[("FLOW_ACTOR_ID", "auditor")],
        )
        .stdout,
    )
    .to_string();
    let report = run_dir.join("verify").join("audit.md");
    write_audit(&report, "warn");
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            auditor.trim(),
            "--report",
            report.to_str().unwrap(),
        ],
        &[("FLOW_ACTOR_ID", "auditor")],
    );
    let out =
        String::from_utf8_lossy(&run(&["check", run_dir.to_str().unwrap(), "protocol"]).stdout)
            .to_string();
    assert!(out.contains("audit sidecar status warn"), "stdout: {out}");
}

#[test]
fn strict_gate_requires_attempts_and_checks() {
    let root = tmp_dir("strict-gate");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "run"
strict = true
attempts = ["run"]
checks = ["result"]
"#,
    );
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "result"
kind = "exists"
gate = "run"
paths = ["result.json"]
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let pre = run(&["check", run_dir.to_str().unwrap(), "run"]);
    assert!(!pre.status.success());
    let pre_out = String::from_utf8_lossy(&pre.stdout);
    assert!(
        pre_out.contains("missing finished run"),
        "stdout: {pre_out}"
    );

    write(&run_dir.join("result.json"), "{}\n");
    let attempt = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "run",
        "--kind",
        "run",
        "--actor",
        "agent:runner",
    ]);
    let finish = assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt.trim(),
    ]);
    assert!(
        finish.lines().any(|line| line == "status\tpassed"),
        "finish: {finish}"
    );
}

#[test]
fn strict_audit_check_requires_typed_mode_items_and_coverage() {
    let root = tmp_dir("strict-audit");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "audit"
strict = true
attempts = ["run", "audit"]
checks = ["audit"]
"#,
    );
    fs::create_dir_all(&run_dir).unwrap();
    let target = run_dir.join("result.json");
    write(&target, "{\"energy\": -1.0}\n");
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "audit"
kind = "audit"
gate = "audit"
mode = "solve"
target = "result.json"
coverage = true
items = ["setup", "limits", "claim"]
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let prod = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "audit",
                "--kind",
                "run",
                "--actor",
                "agent:runner",
            ],
            &[("FLOW_ACTOR_ID", "runner")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &["attempt", "finish", run_dir.to_str().unwrap(), prod.trim()],
        &[("FLOW_ACTOR_ID", "runner")],
    );

    let report = run_dir.join("verify").join("verify_result.md");
    write(&report, "audit findings\n");
    write(
        &report.with_extension("toml"),
        &format!(
            r#"
status = "pass"
mode = "solve"
target = "result.json"
hash = "{}"
author = "attempt:{}"
reviewer = "subagent:reviewer"
brief = "sha256:brief"
coverage = true

[[items]]
id = "setup"
status = "pass"

[[items]]
id = "limits"
status = "pass"

[[items]]
id = "claim"
status = "pass"
"#,
            file_hash(&target),
            prod.trim()
        ),
    );

    let aud = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "audit",
                "--kind",
                "audit",
                "--actor",
                "subagent:reviewer",
            ],
            &[("FLOW_ACTOR_ID", "reviewer")],
        )
        .stdout,
    )
    .to_string();
    let finish = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "finish",
                run_dir.to_str().unwrap(),
                aud.trim(),
                "--report",
                report.to_str().unwrap(),
            ],
            &[("FLOW_ACTOR_ID", "reviewer")],
        )
        .stdout,
    )
    .to_string();
    assert!(
        finish.lines().any(|line| line == "status\tpassed"),
        "finish: {finish}"
    );
}

#[test]
fn strict_audit_check_fails_when_item_missing() {
    let root = tmp_dir("audit-item-missing");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "audit"
strict = true
attempts = ["run", "audit"]
checks = ["audit"]
"#,
    );
    fs::create_dir_all(&run_dir).unwrap();
    let target = run_dir.join("result.json");
    write(&target, "{}\n");
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "audit"
kind = "audit"
gate = "audit"
mode = "solve"
target = "result.json"
coverage = true
items = ["setup", "claim"]
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let prod = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "audit",
                "--kind",
                "run",
                "--actor",
                "agent:runner",
            ],
            &[("FLOW_ACTOR_ID", "runner")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &["attempt", "finish", run_dir.to_str().unwrap(), prod.trim()],
        &[("FLOW_ACTOR_ID", "runner")],
    );

    let report = run_dir.join("verify_result.md");
    write(&report, "audit findings\n");
    write(
        &report.with_extension("toml"),
        &format!(
            r#"
status = "pass"
mode = "solve"
target = "result.json"
hash = "{}"
author = "attempt:{}"
reviewer = "subagent:reviewer"
brief = "sha256:brief"
coverage = true

[[items]]
id = "setup"
status = "pass"
"#,
            file_hash(&target),
            prod.trim()
        ),
    );
    let aud = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "audit",
                "--kind",
                "audit",
                "--actor",
                "subagent:reviewer",
            ],
            &[("FLOW_ACTOR_ID", "reviewer")],
        )
        .stdout,
    )
    .to_string();
    let out = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "finish",
                run_dir.to_str().unwrap(),
                aud.trim(),
                "--report",
                report.to_str().unwrap(),
            ],
            &[("FLOW_ACTOR_ID", "reviewer")],
        )
        .stdout,
    )
    .to_string();
    assert!(out.contains("audit item missing: claim"), "stdout: {out}");
    assert!(
        out.lines().any(|line| line == "status\tfailed"),
        "stdout: {out}"
    );
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
    assert!(
        !output.status.success(),
        "expected failure; stdout: {stdout}"
    );
    assert!(stdout.contains("source changed"), "stdout: {stdout}");
}

#[test]
fn fresh_fails_when_artifact_content_changes() {
    let (run_dir, fig) = fresh_setup("fresh-artifact-change");
    write(&fig, "fig content v2 (tampered)\n");
    let output = run(&["check", run_dir.to_str().unwrap(), "assembly"]);
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    assert!(
        !output.status.success(),
        "expected failure; stdout: {stdout}"
    );
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
    assert!(
        !output.status.success(),
        "expected failure; stdout: {stdout}"
    );
    assert!(stdout.contains("source changed"), "stdout: {stdout}");
}

#[test]
fn status_is_pure_does_not_execute_run_checks() {
    // `flow status` must be a pure read API: it never triggers side effects
    // declared in run-kind checks. The cmd runs at attempt-finish only.
    let root = tmp_dir("status-pure");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    let marker = run_dir.join("marker.txt");
    write(
        &run_dir.join("protocol.toml"),
        &format!(
            "[[checks]]\nid = \"side_effect\"\nkind = \"run\"\ngate = \"source\"\ncmd = \"touch {}\"\n",
            marker.display()
        ),
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(
        !marker.exists(),
        "status executed the run cmd; status must be pure"
    );
}

#[test]
fn status_help_is_pure() {
    let root = tmp_dir("status-help");
    let target = root.join("--help");
    let out = assert_ok(&["status", target.to_str().unwrap(), "--help"]);
    assert!(out.contains("usage: harness-flow status"), "stdout: {out}");
    assert!(
        !target.exists(),
        "status --help must not create or rebuild a flow directory"
    );
}

#[test]
fn attempt_finish_executes_run_checks_and_caches_result() {
    let root = tmp_dir("run-cached");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    let marker = run_dir.join("ran.txt");
    write(
        &run_dir.join("protocol.toml"),
        &format!(
            "[[checks]]\nid = \"side_effect\"\nkind = \"run\"\ngate = \"source\"\ncmd = \"touch {}\"\n",
            marker.display()
        ),
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
        "source",
        "--kind",
        "run",
        "--actor",
        "agent:main",
    ]);
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt.trim(),
    ]);
    assert!(marker.exists(), "attempt finish must execute run cmd");
    let state = fs::read_to_string(run_dir.join("progress").join("state.toml")).unwrap();
    assert!(state.contains("side_effect"), "run result must be cached");
}

#[test]
fn audit_detects_report_tampering_after_finish() {
    let root = tmp_dir("audit-tamper");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        "[[checks]]\nid = \"audit_x\"\nkind = \"audit\"\ngate = \"source\"\n",
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let prod = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "source",
                "--kind",
                "run",
                "--actor",
                "agent:producer",
            ],
            &[("FLOW_ACTOR_ID", "producer-id")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &["attempt", "finish", run_dir.to_str().unwrap(), prod.trim()],
        &[("FLOW_ACTOR_ID", "producer-id")],
    );
    let report = run_dir.join("verify_source.md");
    write_audit(&report, "pass");
    let aud = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "source",
                "--kind",
                "audit",
                "--actor",
                "agent:auditor",
            ],
            &[("FLOW_ACTOR_ID", "auditor-id")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            aud.trim(),
            "--report",
            report.to_str().unwrap(),
        ],
        &[("FLOW_ACTOR_ID", "auditor-id")],
    );
    assert_ok(&["require", run_dir.to_str().unwrap(), "source"]);
    // Tamper with the audit report after finish.
    write(&report, "audit: TAMPERED\n");
    let err = assert_fail(&["require", run_dir.to_str().unwrap(), "source"]);
    assert!(err.contains("not passed"), "stderr: {err}");
    let post = run(&["check", run_dir.to_str().unwrap(), "source"]);
    let stdout = String::from_utf8_lossy(&post.stdout).to_string();
    assert!(
        stdout.contains("mutated"),
        "expected mutated marker; stdout: {stdout}"
    );
}

#[test]
fn status_lists_gates_in_dag_order_with_next_marker() {
    // Template declares c → b → a (requires). Alphabetical order is a, b, c;
    // DAG order must be a, b, c (post-order over requires), with ▶ on the
    // first runnable gate.
    let root = tmp_dir("dag-order");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[[gates]]
id = "c"
requires = ["b"]

[[gates]]
id = "b"
requires = ["a"]

[[gates]]
id = "a"
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let status = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
    let gates: Vec<&str> = status
        .lines()
        .filter_map(|l| l.split('\t').next())
        .filter(|first| ["a", "b", "c"].contains(first))
        .collect();
    assert_eq!(gates, vec!["a", "b", "c"], "status: {status}");
    assert!(
        status
            .lines()
            .any(|l| l.starts_with("a\t") && l.contains("▶")),
        "▶ should mark gate `a` (first runnable); status: {status}"
    );
    assert!(
        !status
            .lines()
            .any(|l| l.starts_with("b\t") && l.contains("▶")),
        "only the first runnable gate gets ▶"
    );
}

#[test]
fn status_default_is_terse_and_full_keeps_gate_table() {
    let root = tmp_dir("status-terse");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        r#"
[flow]
id = "terse_demo"

[[gates]]
id = "source"

[[gates]]
id = "close"
requires = ["source"]
"#,
    );
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "source_file"
kind = "exists"
gate = "source"
paths = ["source.txt"]
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let terse = assert_ok(&["status", run_dir.to_str().unwrap()]);
    assert!(terse.contains("flow terse_demo"), "status: {terse}");
    assert!(terse.contains("gate source failed"), "status: {terse}");
    assert!(
        terse.contains("blocker source_file: missing: source.txt"),
        "status: {terse}"
    );
    assert!(terse.contains("next flow attempt start"), "status: {terse}");
    assert!(
        !terse.lines().any(|line| line.starts_with("source\t")),
        "default status should not print the full gate table: {terse}"
    );

    let full = assert_ok(&["status", run_dir.to_str().unwrap(), "--full"]);
    assert!(
        full.lines().any(|line| line.starts_with("source\tfailed")),
        "status: {full}"
    );
}

#[test]
fn protocol_rejects_unknown_check_kind_at_parse_time() {
    let root = tmp_dir("typed-kind");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "bad"
kind = "manifest_fields"
gate = "source"
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let err = assert_fail(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(err.contains("protocol.toml parse error"), "stderr: {err}");
    assert!(err.contains("manifest_fields"), "stderr: {err}");
}

#[test]
fn protocol_rejects_duplicate_check_ids() {
    let root = tmp_dir("duplicate-check-id");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "audit"
kind = "audit"
gate = "source"

[[checks]]
id = "audit"
kind = "exists"
gate = "source"
paths = ["artifact.txt"]
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let err = assert_fail(&["check", run_dir.to_str().unwrap(), "source"]);
    assert!(err.contains("duplicate check id audit"), "stderr: {err}");
}

#[test]
fn protocol_rejects_producer_on_artifactless_check() {
    let root = tmp_dir("producer-artifactless");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"close\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "entry"
kind = "run"
gate = "close"
cmd = "true"
producer = "run"
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let err = assert_fail(&["check", run_dir.to_str().unwrap(), "close"]);
    assert!(
        err.contains("check entry cannot use producer with run"),
        "stderr: {err}"
    );
}

#[test]
fn attempt_start_rejects_unknown_kind() {
    let root = tmp_dir("attempt-kind");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"run\"\n");
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let err = assert_fail(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "run",
        "--kind",
        "probe",
        "--actor",
        "agent:x",
    ]);
    assert!(err.contains("unknown attempt kind: probe"), "stderr: {err}");
}

#[test]
fn cover_check_requires_exact_observed_path_set() {
    let root = tmp_dir("cover");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"assemble\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "cells"
kind = "cover"
gate = "assemble"
pattern = "cells/*/manifest.json"
paths = [
  "cells/cell-a/manifest.json",
  "cells/cell-b/manifest.json",
]
"#,
    );
    write(
        &run_dir.join("cells/cell-a/manifest.json"),
        "{\"ok\": true}\n",
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let missing = run(&["check", run_dir.to_str().unwrap(), "assemble"]);
    let missing_out = String::from_utf8_lossy(&missing.stdout).to_string();
    assert!(!missing.status.success(), "stdout: {missing_out}");
    assert!(
        missing_out.contains("missing: cells/cell-b/manifest.json"),
        "stdout: {missing_out}"
    );

    write(
        &run_dir.join("cells/cell-b/manifest.json"),
        "{\"ok\": true}\n",
    );
    let pass = assert_ok(&["check", run_dir.to_str().unwrap(), "assemble"]);
    assert!(pass.contains("2 path(s) covered"), "stdout: {pass}");

    write(
        &run_dir.join("cells/trial/manifest.json"),
        "{\"ok\": true}\n",
    );
    let extra = run(&["check", run_dir.to_str().unwrap(), "assemble"]);
    let extra_out = String::from_utf8_lossy(&extra.stdout).to_string();
    assert!(!extra.status.success(), "stdout: {extra_out}");
    assert!(
        extra_out.contains("extra: cells/trial/manifest.json"),
        "stdout: {extra_out}"
    );
}

#[cfg(unix)]
#[test]
fn cover_check_skips_symlinked_directories() {
    use std::os::unix::fs::symlink;

    let root = tmp_dir("cover-symlink");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    let external = root.join("external");
    write(&template, "[[gates]]\nid = \"assemble\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "cells"
kind = "cover"
gate = "assemble"
pattern = "cells/*/manifest.json"
paths = ["cells/cell-a/manifest.json"]
"#,
    );
    write(
        &run_dir.join("cells/cell-a/manifest.json"),
        "{\"ok\": true}\n",
    );
    write(&external.join("leak/manifest.json"), "{\"ok\": false}\n");
    symlink(&external, run_dir.join("cells/link")).unwrap();
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let pass = assert_ok(&["check", run_dir.to_str().unwrap(), "assemble"]);
    assert!(pass.contains("1 path(s) covered"), "stdout: {pass}");
}

#[test]
fn producer_check_rejects_trial_artifact() {
    let root = tmp_dir("producer");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"run\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[checks]]
id = "cells"
kind = "cover"
gate = "run"
producer = "run"
pattern = "cells/*/manifest.json"
paths = ["cells/cell-a/manifest.json"]
"#,
    );
    write(
        &run_dir.join("cells/cell-a/manifest.json"),
        "{\"energy\": -1.0}\n",
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let trial = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "run",
        "--kind",
        "trial",
        "--actor",
        "agent:trial",
    ]);
    assert_ok(&[
        "artifact",
        "add",
        run_dir.to_str().unwrap(),
        "cell",
        run_dir.join("cells/cell-a/manifest.json").to_str().unwrap(),
        "--kind",
        "manifest",
        "--producer",
        trial.trim(),
    ]);
    let rejected = run(&["check", run_dir.to_str().unwrap(), "run"]);
    let rejected_out = String::from_utf8_lossy(&rejected.stdout).to_string();
    assert!(!rejected.status.success(), "stdout: {rejected_out}");
    assert!(
        rejected_out.contains("produced by trial; check requires run"),
        "stdout: {rejected_out}"
    );

    let prod = assert_ok(&[
        "attempt",
        "start",
        run_dir.to_str().unwrap(),
        "run",
        "--kind",
        "run",
        "--actor",
        "agent:run",
    ]);
    assert_ok(&[
        "artifact",
        "add",
        run_dir.to_str().unwrap(),
        "cell",
        run_dir.join("cells/cell-a/manifest.json").to_str().unwrap(),
        "--kind",
        "manifest",
        "--producer",
        prod.trim(),
    ]);
    let pass = assert_ok(&["check", run_dir.to_str().unwrap(), "run"]);
    assert!(pass.contains("1 path(s) covered"), "stdout: {pass}");
}

#[test]
fn support_check_requires_claim_fields() {
    let root = tmp_dir("support");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"assemble\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[claims]]
id = "energy"
statement = "Energy is supported."
fields = [
  "cells/*/manifest.json:energy",
  "cells/*/manifest.json:stderr",
]

[[checks]]
id = "energy"
kind = "support"
gate = "assemble"
claims = ["energy"]
"#,
    );
    write(
        &run_dir.join("cells/cell-a/manifest.json"),
        "{\"energy\": -1.0}\n",
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let missing = run(&["check", run_dir.to_str().unwrap(), "assemble"]);
    let missing_out = String::from_utf8_lossy(&missing.stdout).to_string();
    assert!(!missing.status.success(), "stdout: {missing_out}");
    assert!(
        missing_out.contains("cells/cell-a/manifest.json missing stderr"),
        "stdout: {missing_out}"
    );

    write(
        &run_dir.join("cells/cell-a/manifest.json"),
        "{\"energy\": -1.0, \"stderr\": 0.01}\n",
    );
    let pass = assert_ok(&["check", run_dir.to_str().unwrap(), "assemble"]);
    assert!(pass.contains("2 field(s) supported"), "stdout: {pass}");
}

#[test]
fn run_check_can_use_declared_entry_command() {
    let root = tmp_dir("entry");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"close\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[entry]
run = "printf run"
help = "printf help"
dry = "printf dry"

[[checks]]
id = "entry"
kind = "run"
gate = "close"
entry = "help"
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
        "close",
        "--kind",
        "report",
        "--actor",
        "agent:report",
    ]);
    let out = assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt.trim(),
    ]);
    assert!(
        out.contains("ok\tentry\texit 0: printf help"),
        "stdout: {out}"
    );
}

#[test]
fn status_json_reports_scope_verdict() {
    let root = tmp_dir("verdict");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"close\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[artifact]
scope = "snapshot"
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
        "close",
        "--kind",
        "run",
        "--actor",
        "agent:run",
    ]);
    assert_ok(&[
        "attempt",
        "finish",
        run_dir.to_str().unwrap(),
        attempt.trim(),
    ]);

    let out = assert_ok(&["status", run_dir.to_str().unwrap(), "--json"]);
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    assert_eq!(v["scope"], "snapshot");
    assert_eq!(v["verdict"], "muted");
}

#[test]
fn verify_sidecar_verdicts_surface_in_status_json() {
    // Audit subagent writes verify_*.md + sibling verify_*.toml. The sidecar
    // carries [[verdicts]] claim/status entries; flow parses them at
    // attempt-finish and exposes them via `flow status --json` so renderers
    // never grep prose for per-claim chip status.
    let root = tmp_dir("verdicts");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(&template, "[[gates]]\nid = \"source\"\n");
    fs::create_dir_all(&run_dir).unwrap();
    write(
        &run_dir.join("protocol.toml"),
        r#"
[[claims]]
id = "claim.alpha"
statement = "Alpha holds."

[[claims]]
id = "claim.beta"
statement = "Beta is bounded."

[[checks]]
id = "audit_x"
kind = "audit"
gate = "source"
"#,
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);

    let prod = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "source",
                "--kind",
                "run",
                "--actor",
                "agent:p",
            ],
            &[("FLOW_ACTOR_ID", "producer")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &["attempt", "finish", run_dir.to_str().unwrap(), prod.trim()],
        &[("FLOW_ACTOR_ID", "producer")],
    );

    let report = run_dir.join("verify_source.md");
    write(&report, "audit findings\n");
    let sidecar = run_dir.join("verify_source.toml");
    write(
        &sidecar,
        r#"
status = "pass"

[[verdicts]]
claim = "claim.alpha"
status = "pass"

[[verdicts]]
claim = "claim.beta"
status = "warn"
note = "within 2σ of reference"
"#,
    );

    let aud = String::from_utf8_lossy(
        &run_with_env(
            &[
                "attempt",
                "start",
                run_dir.to_str().unwrap(),
                "source",
                "--kind",
                "audit",
                "--actor",
                "agent:a",
            ],
            &[("FLOW_ACTOR_ID", "auditor")],
        )
        .stdout,
    )
    .to_string();
    run_with_env(
        &[
            "attempt",
            "finish",
            run_dir.to_str().unwrap(),
            aud.trim(),
            "--report",
            report.to_str().unwrap(),
        ],
        &[("FLOW_ACTOR_ID", "auditor")],
    );

    let out = assert_ok(&["status", run_dir.to_str().unwrap(), "--json"]);
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    let claims = v["claims"].as_array().expect("claims array");
    assert_eq!(claims.len(), 2);
    let alpha = claims.iter().find(|c| c["id"] == "claim.alpha").unwrap();
    assert_eq!(alpha["verdict"], "pass");
    let beta = claims.iter().find(|c| c["id"] == "claim.beta").unwrap();
    assert_eq!(beta["verdict"], "warn");
    assert_eq!(beta["note"], "within 2σ of reference");
}

#[test]
fn status_json_emits_parseable_structure() {
    let root = tmp_dir("status-json");
    let template = root.join("template.toml");
    let run_dir = root.join("run");
    write(
        &template,
        "[flow]\nid = \"demo\"\n[[gates]]\nid = \"source\"\n",
    );
    assert_ok(&[
        "init",
        run_dir.to_str().unwrap(),
        "--template",
        template.to_str().unwrap(),
    ]);
    let out = assert_ok(&["status", run_dir.to_str().unwrap(), "--json"]);
    let v: serde_json::Value =
        serde_json::from_str(&out).expect("status --json must be valid JSON");
    assert_eq!(v["flow_id"], "demo");
    assert_eq!(v["gates"][0]["id"], "source");
    assert_eq!(v["gates"][0]["status"], "pending");
    assert_eq!(v["gates"][0]["runnable"], true);
    assert_eq!(v["next"][0], "source");
}
