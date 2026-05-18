use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process;
use std::process::Command;
use std::thread;
use std::time::Duration;
use std::time::Instant;
use std::time::{SystemTime, UNIX_EPOCH};

type Result<T> = std::result::Result<T, String>;

const GATE_PENDING: &str = "pending";
const GATE_PASSED: &str = "passed";
const GATE_FAILED: &str = "failed";
const GATE_INVALIDATED: &str = "invalidated";
const FLOW_TEMPLATE_FILE: &str = "flow.toml";
const PROTOCOL_FILE: &str = "protocol.toml";

// One-word generic check kinds. Each names what the check does, never what
// artifact it touches. Domain semantics live in protocol.toml fields.
const CHECK_AUDIT: &str = "audit"; // verifier ran with a distinct actor
const CHECK_RUN: &str = "run"; // external command exits zero
const CHECK_EXISTS: &str = "exists"; // declared fields/paths are present
const CHECK_AGREE: &str = "agree"; // declared values match across sources
const CHECK_NEAR: &str = "near"; // numeric within tolerance of reference
const CHECK_FRESH: &str = "fresh"; // artifact newer than declared sources

#[derive(Clone, Debug, Default)]
struct Gate {
    requires: Vec<String>,
    invalidates: Vec<String>,
}

#[derive(Clone, Debug)]
struct Attempt {
    seq: u64,
    gate: String,
    kind: String,
    actor: String,
    executor: Option<String>,
    command: Option<String>,
    report: Option<String>,
    finished: bool,
}

#[derive(Clone, Debug)]
struct Artifact {
    path: String,
    kind: String,
    producer: Option<String>,
    hash: String,
}

#[derive(Clone, Debug)]
struct Override {
    check: String,
    gate: String,
    reason: String,
    actor: String,
    at: String,
}

#[derive(Debug, Default)]
struct State {
    seq: u64,
    flow_id: Option<String>,
    gates: BTreeMap<String, Gate>,
    gate_status: BTreeMap<String, String>,
    attempts: BTreeMap<String, Attempt>,
    artifacts: BTreeMap<String, Artifact>,
    overrides: Vec<Override>,
    children: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(untagged)]
enum Value {
    String(String),
    Array(Vec<String>),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Event {
    #[serde(rename = "event")]
    kind: String,
    #[serde(flatten)]
    fields: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize)]
struct GateSpec {
    id: String,
    #[serde(default)]
    requires: Vec<String>,
    #[serde(default)]
    invalidates: Vec<String>,
}

#[derive(Deserialize)]
struct FlowTemplate {
    flow: Option<FlowTemplateHeader>,
    #[serde(default)]
    gates: Vec<GateSpec>,
}

#[derive(Deserialize)]
struct FlowTemplateHeader {
    id: Option<String>,
}

#[derive(Deserialize, Clone, Debug)]
struct Check {
    id: String,
    kind: String,
    gate: String,
    #[serde(default)]
    cmd: Option<String>,
    #[serde(default)]
    fields: Vec<String>,
    #[serde(default)]
    paths: Vec<String>,
    #[serde(default)]
    against: Vec<String>,
    #[serde(default)]
    compare: Vec<Compare>,
}

#[derive(Deserialize, Clone, Debug)]
struct Compare {
    actual: ValueRef,
    reference: ValueRef,
    #[serde(default)]
    uncertainty: Option<ValueRef>,
    tolerance: Tolerance,
}

#[derive(Deserialize, Clone, Debug)]
struct ValueRef {
    path: String,
    field: String,
}

#[derive(Deserialize, Clone, Debug)]
struct Tolerance {
    #[serde(default)]
    abs: Option<f64>,
    #[serde(default)]
    rel: Option<f64>,
    #[serde(default)]
    sigma: Option<f64>,
}

#[derive(Deserialize, Default)]
struct Protocol {
    #[serde(default, rename = "checks")]
    checks: Vec<Check>,
}

#[derive(Clone, Debug)]
struct CheckResult {
    id: String,
    pass: bool,
    detail: String,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        process::exit(1);
    }
}

fn run() -> Result<()> {
    let mut args = env::args().skip(1).collect::<Vec<_>>();
    if args.is_empty() {
        return Err(usage());
    }

    match args.remove(0).as_str() {
        "init" => cmd_init(&args),
        "status" => cmd_status(&args),
        "next" => cmd_next(&args),
        "require" => cmd_require(&args),
        "artifact" => cmd_artifact(&args),
        "attempt" => cmd_attempt(&args),
        "check" => cmd_check(&args),
        "override" => cmd_override(&args),
        "invalidate" => cmd_invalidate(&args),
        "attach" => cmd_attach(&args),
        "-h" | "--help" | "help" => {
            println!("{}", usage());
            Ok(())
        }
        other => Err(format!("unknown command: {other}\n{}", usage())),
    }
}

fn usage() -> String {
    "usage: harness-flow <init|status|next|require|artifact|attempt|check|override|invalidate|attach> ..."
        .to_string()
}

fn cmd_init(args: &[String]) -> Result<()> {
    if args.len() != 3 || args[1] != "--template" {
        return Err("usage: harness-flow init <dir> --template <template.toml>".to_string());
    }
    let dir = Path::new(&args[0]);
    let template = Path::new(&args[2]);
    let template_text = fs::read_to_string(template).map_err(|e| e.to_string())?;
    let (flow_id, gates) = parse_template_text(&template_text)?;

    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    with_flow_lock(dir, || {
        let events = events_path(dir);
        if events.exists() {
            return Err(format!("flow already exists: {}", dir.display()));
        }
        persist_flow_template(dir, &template_text)?;

        append_event(
            dir,
            &event(
                "flow_initialized",
                vec![
                    (
                        "flow_id",
                        Value::String(flow_id.unwrap_or_else(|| flow_id_from_path(dir))),
                    ),
                    ("created_at", Value::String(now_id())),
                ],
            ),
        )?;
        for gate in gates {
            append_event(
                dir,
                &event(
                    "gate_added",
                    vec![
                        ("id", Value::String(gate.id)),
                        ("requires", Value::Array(gate.requires)),
                        ("invalidates", Value::Array(gate.invalidates)),
                    ],
                ),
            )?;
        }
        rebuild(dir)?;
        Ok(())
    })
}

fn cmd_status(args: &[String]) -> Result<()> {
    if args.is_empty() {
        return Err("usage: harness-flow status <dir> [--recursive]".to_string());
    }
    let dir = Path::new(&args[0]);
    let recursive = args.iter().skip(1).any(|arg| arg == "--recursive");
    let state = with_flow_lock(dir, || rebuild(dir))?;
    print_status(dir, &state, 0, recursive)
}

fn cmd_next(args: &[String]) -> Result<()> {
    if args.len() != 1 {
        return Err("usage: harness-flow next <dir>".to_string());
    }
    let dir = Path::new(&args[0]);
    let dir_arg = &args[0];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    for gate in ready_gates(&state) {
        println!("{gate}");
        println!(
            "  flow attempt start {dir_arg} {gate} --kind <kind> --actor agent:<role>"
        );
    }
    Ok(())
}

fn cmd_require(args: &[String]) -> Result<()> {
    if args.len() != 2 {
        return Err("usage: harness-flow require <dir> <gate>".to_string());
    }
    let dir = Path::new(&args[0]);
    let gate = &args[1];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    if gate_passed(&state, gate) {
        Ok(())
    } else {
        Err(format!("{gate} not passed"))
    }
}

fn cmd_artifact(args: &[String]) -> Result<()> {
    if args.len() < 5 || args[0] != "add" {
        return Err(
            "usage: harness-flow artifact add <dir> <id> <path> --kind <kind> [--producer <attempt>]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[1]);
    let id = args[2].clone();
    let path = Path::new(&args[3]);
    let kind = required_option(args, "--kind")?;
    let producer = option_value(args, "--producer");
    let hash = file_hash(path)?;
    with_flow_lock(dir, || {
        ensure_flow(dir)?;
        let state = rebuild(dir)?;
        if let Some(producer) = &producer {
            if !state.attempts.contains_key(producer) {
                return Err(format!("unknown producer attempt: {producer}"));
            }
            if !attempt_is_current(&state, producer) {
                return Err(format!("stale producer attempt: {producer}"));
            }
        }
        let invalidated = match state.artifacts.get(&id) {
            Some(existing) if existing.hash != hash => {
                invalidation_closure(&state, invalidation_roots(&state, &id)?)
            }
            _ => Vec::new(),
        };
        append_event(
            dir,
            &event(
                "artifact_added",
                vec![
                    ("id", Value::String(id.clone())),
                    ("path", Value::String(path.display().to_string())),
                    ("kind", Value::String(kind.clone())),
                    ("hash", Value::String(hash.clone())),
                    (
                        "producer",
                        Value::String(producer.clone().unwrap_or_default()),
                    ),
                ],
            ),
        )?;
        if !invalidated.is_empty() {
            append_event(
                dir,
                &event(
                    "gate_invalidated",
                    vec![
                        ("from", Value::String(id.clone())),
                        ("targets", Value::Array(invalidated)),
                    ],
                ),
            )?;
        }
        rebuild(dir)?;
        Ok(())
    })
}

fn cmd_attempt(args: &[String]) -> Result<()> {
    if args.is_empty() {
        return Err("usage: harness-flow attempt <start|finish> ...".to_string());
    }
    match args[0].as_str() {
        "start" => cmd_attempt_start(args),
        "finish" => cmd_attempt_finish(args),
        _ => Err("usage: harness-flow attempt <start|finish> ...".to_string()),
    }
}

fn cmd_attempt_start(args: &[String]) -> Result<()> {
    if args.len() < 6 {
        return Err(
            "usage: harness-flow attempt start <dir> <gate> --kind <kind> --actor <actor> [--executor <exec>] [--command <cmd>]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[1]);
    let gate = args[2].clone();
    let kind = required_option(args, "--kind")?;
    let actor = required_option(args, "--actor")?;
    let executor = option_value(args, "--executor").unwrap_or_else(|| "local".to_string());
    let command = option_value(args, "--command").unwrap_or_default();
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        if !state.gates.contains_key(&gate) {
            return Err(format!("unknown gate: {gate}"));
        }
        if !requirements_passed(&state, &gate) {
            return Err(format!("{gate} requirements not passed"));
        }

        let id = format!("a{}", now_id());
        append_event(
            dir,
            &event(
                "attempt_started",
                vec![
                    ("id", Value::String(id.clone())),
                    ("gate", Value::String(gate)),
                    ("kind", Value::String(kind)),
                    ("actor", Value::String(actor)),
                    ("executor", Value::String(executor)),
                    ("command", Value::String(command)),
                ],
            ),
        )?;
        rebuild(dir)?;
        println!("{id}");
        Ok(())
    })
}

fn cmd_attempt_finish(args: &[String]) -> Result<()> {
    if args.len() < 3 {
        return Err(
            "usage: harness-flow attempt finish <dir> <attempt> [--report <path>]".to_string(),
        );
    }
    let dir = Path::new(&args[1]);
    let id = args[2].clone();
    let report = option_value(args, "--report");
    if let Some(report_path) = &report {
        if !Path::new(report_path).exists() {
            return Err(format!("report not found: {report_path}"));
        }
    }
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        let attempt = state
            .attempts
            .get(&id)
            .ok_or_else(|| format!("unknown attempt: {id}"))?
            .clone();
        if attempt.finished {
            return Err(format!("attempt already finished: {id}"));
        }
        if !attempt_is_current(&state, &id) {
            return Err(format!("stale attempt: {id}"));
        }

        // Record finish before evaluating so checks see this attempt as finished.
        let report_value = report.clone().unwrap_or_default();
        append_event(
            dir,
            &event(
                "attempt_finished",
                vec![
                    ("id", Value::String(id.clone())),
                    ("report", Value::String(report_value)),
                ],
            ),
        )?;
        let state = rebuild(dir)?;
        let (status, results) = evaluate_gate(dir, &state, &attempt.gate);
        append_event(
            dir,
            &event(
                "gate_evaluated",
                vec![
                    ("gate", Value::String(attempt.gate.clone())),
                    ("attempt", Value::String(id.clone())),
                    ("status", Value::String(status.clone())),
                    (
                        "results",
                        Value::Array(
                            results
                                .iter()
                                .map(|r| {
                                    format!(
                                        "{}:{}:{}",
                                        r.id,
                                        if r.pass { "pass" } else { "fail" },
                                        r.detail.replace(':', " ")
                                    )
                                })
                                .collect(),
                        ),
                    ),
                ],
            ),
        )?;
        rebuild(dir)?;
        for r in &results {
            let mark = if r.pass { "ok" } else { "fail" };
            println!("{mark}\t{}\t{}", r.id, r.detail);
        }
        println!("status\t{status}");
        Ok(())
    })
}

fn cmd_check(args: &[String]) -> Result<()> {
    if args.len() != 2 {
        return Err("usage: harness-flow check <dir> <gate>".to_string());
    }
    let dir = Path::new(&args[0]);
    let gate = &args[1];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    if !state.gates.contains_key(gate) {
        return Err(format!("unknown gate: {gate}"));
    }
    let (status, results) = evaluate_gate(dir, &state, gate);
    for r in &results {
        let mark = if r.pass { "ok" } else { "fail" };
        println!("{mark}\t{}\t{}", r.id, r.detail);
    }
    println!("status\t{status}");
    if status != GATE_PASSED {
        process::exit(1);
    }
    Ok(())
}

// Agent invokes only after presenting the bypass via the host's option API
// and getting user confirmation; the CLI itself is non-interactive.
fn cmd_override(args: &[String]) -> Result<()> {
    if args.len() < 3 {
        return Err(
            "usage: harness-flow override <dir> <check-id> --reason <text> [--actor <actor>]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[0]);
    let check_id = args[1].clone();
    let reason = required_option(args, "--reason")?;
    let actor = option_value(args, "--actor").unwrap_or_else(|| "user".to_string());
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        let protocol = load_protocol(dir)?;
        let check = protocol
            .checks
            .iter()
            .find(|c| c.id == check_id)
            .ok_or_else(|| format!("unknown check: {check_id}"))?;
        // The gate must exist; ensures the override targets a real gate.
        if !state.gates.contains_key(&check.gate) {
            return Err(format!("check {check_id} targets unknown gate {}", check.gate));
        }
        append_event(
            dir,
            &event(
                "override_recorded",
                vec![
                    ("check", Value::String(check_id.clone())),
                    ("gate", Value::String(check.gate.clone())),
                    ("reason", Value::String(reason.clone())),
                    ("actor", Value::String(actor)),
                    ("at", Value::String(now_id())),
                ],
            ),
        )?;
        let state = rebuild(dir)?;
        // Re-evaluate the affected gate so its status reflects the override.
        let (status, _) = evaluate_gate(dir, &state, &check.gate);
        append_event(
            dir,
            &event(
                "gate_evaluated",
                vec![
                    ("gate", Value::String(check.gate.clone())),
                    ("attempt", Value::String(String::new())),
                    ("status", Value::String(status.clone())),
                    ("results", Value::Array(vec![])),
                ],
            ),
        )?;
        rebuild(dir)?;
        println!("override recorded: {check_id} (gate {}) → status {}", check.gate, status);
        Ok(())
    })
}

fn cmd_invalidate(args: &[String]) -> Result<()> {
    if args.len() < 3 {
        return Err(
            "usage: harness-flow invalidate <dir> --from <artifact-or-gate> [--gates a,b]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[0]);
    let from = required_option(args, "--from")?;
    let explicit = option_list(args, "--gates")?;
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        let mut targets = explicit;
        if targets.is_empty() {
            targets = invalidation_roots(&state, &from)?;
        }
        targets = invalidation_closure(&state, targets);
        if targets.is_empty() {
            return Err(format!("{from} has no invalidation targets"));
        }
        append_event(
            dir,
            &event(
                "gate_invalidated",
                vec![
                    ("from", Value::String(from)),
                    ("targets", Value::Array(targets)),
                ],
            ),
        )?;
        rebuild(dir)?;
        Ok(())
    })
}

fn invalidation_roots(state: &State, from: &str) -> Result<Vec<String>> {
    if let Some(artifact) = state.artifacts.get(from) {
        if let Some(producer) = &artifact.producer {
            if let Some(attempt) = state.attempts.get(producer) {
                return Ok(vec![attempt.gate.clone()]);
            }
        }
        if state.gates.contains_key(from) {
            return Ok(vec![from.to_string()]);
        }
        return Err(format!("{from} artifact has no producing gate"));
    }

    if let Some(gate) = state.gates.get(from) {
        return Ok(gate.invalidates.clone());
    }

    Err(format!("{from} is not an artifact or gate"))
}

fn invalidation_closure(state: &State, roots: Vec<String>) -> Vec<String> {
    let mut seen = BTreeSet::new();
    let mut stack = roots;
    while let Some(gate) = stack.pop() {
        if !state.gates.contains_key(&gate) || !seen.insert(gate.clone()) {
            continue;
        }
        if let Some(spec) = state.gates.get(&gate) {
            stack.extend(spec.invalidates.iter().cloned());
        }
        for (candidate, spec) in &state.gates {
            if spec.requires.iter().any(|required| required == &gate) {
                stack.push(candidate.clone());
            }
        }
    }
    seen.into_iter().collect()
}

fn cmd_attach(args: &[String]) -> Result<()> {
    if args.len() != 4 || args[2] != "--as" || args[3] != "child" {
        return Err("usage: harness-flow attach <parent-dir> <child-dir> --as child".to_string());
    }
    let parent = Path::new(&args[0]);
    let child = Path::new(&args[1]);
    if !events_path(child).exists() {
        return Err(format!("child flow not found: {}", child.display()));
    }
    let child = fs::canonicalize(child).map_err(|e| e.to_string())?;
    with_flow_lock(parent, || {
        ensure_flow(parent)?;
        append_event(
            parent,
            &event(
                "child_attached",
                vec![("path", Value::String(child.display().to_string()))],
            ),
        )?;
        rebuild(parent)?;
        Ok(())
    })
}

struct FlowLock {
    path: PathBuf,
}

impl Drop for FlowLock {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn with_flow_lock<T>(dir: &Path, f: impl FnOnce() -> Result<T>) -> Result<T> {
    let _lock = acquire_flow_lock(dir)?;
    f()
}

fn acquire_flow_lock(dir: &Path) -> Result<FlowLock> {
    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    let path = progress_dir(dir).join(".lock");
    let start = Instant::now();
    let timeout = lock_timeout();

    loop {
        match fs::create_dir(&path) {
            Ok(()) => {
                let owner = path.join("owner");
                let _ = fs::write(owner, format!("pid={}\n", process::id()));
                return Ok(FlowLock { path });
            }
            Err(err) if err.kind() == std::io::ErrorKind::AlreadyExists => {
                if start.elapsed() >= timeout {
                    return Err(format!(
                        "flow lock is held: {}. Another writer is updating this flow.",
                        path.display()
                    ));
                }
                thread::sleep(Duration::from_millis(25));
            }
            Err(err) => return Err(err.to_string()),
        }
    }
}

fn lock_timeout() -> Duration {
    env::var("HARNESS_FLOW_LOCK_TIMEOUT_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .map(Duration::from_millis)
        .unwrap_or_else(|| Duration::from_secs(30))
}

fn rebuild(dir: &Path) -> Result<State> {
    let events = read_events(dir)?;
    let mut state = State::default();
    for event in events {
        apply_event(&mut state, event)?;
    }
    write_state(dir, &state)?;
    Ok(state)
}

fn read_events(dir: &Path) -> Result<Vec<Event>> {
    let path = events_path(dir);
    if !path.exists() {
        return Err(format!("flow not found: {}", dir.display()));
    }
    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    text.lines()
        .filter(|line| !line.trim().is_empty())
        .map(parse_event)
        .collect()
}

fn ensure_flow(dir: &Path) -> Result<()> {
    if events_path(dir).exists() {
        Ok(())
    } else {
        Err(format!("flow not found: {}", dir.display()))
    }
}

fn apply_event(state: &mut State, event: Event) -> Result<()> {
    state.seq += 1;
    let event_seq = state.seq;
    match event.kind.as_str() {
        "flow_initialized" => {
            state.flow_id = event.string("flow_id");
        }
        "gate_added" => {
            let id = event.required_string("id")?;
            state.gates.insert(
                id.clone(),
                Gate {
                    requires: event.array("requires"),
                    invalidates: event.array("invalidates"),
                },
            );
            state
                .gate_status
                .entry(id)
                .or_insert_with(|| GATE_PENDING.to_string());
        }
        "attempt_started" => {
            let id = event.required_string("id")?;
            state.attempts.insert(
                id,
                Attempt {
                    seq: event_seq,
                    gate: event.required_string("gate")?,
                    kind: event.required_string("kind")?,
                    actor: event.required_string("actor")?,
                    executor: event.string("executor").filter(|v| !v.is_empty()),
                    command: event.string("command").filter(|v| !v.is_empty()),
                    report: None,
                    finished: false,
                },
            );
        }
        "attempt_finished" => {
            let id = event.required_string("id")?;
            let report = event.string("report").filter(|v| !v.is_empty());
            let attempt = state
                .attempts
                .get_mut(&id)
                .ok_or_else(|| format!("unknown attempt in event log: {id}"))?;
            attempt.report = report;
            attempt.finished = true;
        }
        "gate_evaluated" => {
            let gate = event.required_string("gate")?;
            let status = event.required_string("status")?;
            state.gate_status.insert(gate, status);
        }
        "artifact_added" => {
            let id = event.required_string("id")?;
            state.artifacts.insert(
                id,
                Artifact {
                    path: event.required_string("path")?,
                    kind: event.required_string("kind")?,
                    producer: event.string("producer").filter(|v| !v.is_empty()),
                    hash: event.required_string("hash")?,
                },
            );
        }
        "gate_invalidated" => {
            for gate in event.array("targets") {
                state.gate_status.insert(gate, GATE_INVALIDATED.to_string());
            }
        }
        "override_recorded" => {
            state.overrides.push(Override {
                check: event.required_string("check")?,
                gate: event.required_string("gate")?,
                reason: event.required_string("reason")?,
                actor: event.required_string("actor")?,
                at: event.required_string("at")?,
            });
        }
        "child_attached" => {
            state.children.push(event.required_string("path")?);
        }
        other => return Err(format!("unknown event kind: {other}")),
    }
    Ok(())
}

fn print_status(dir: &Path, state: &State, indent: usize, recursive: bool) -> Result<()> {
    let pad = " ".repeat(indent);
    let label = state
        .flow_id
        .as_deref()
        .unwrap_or_else(|| dir.file_name().and_then(|v| v.to_str()).unwrap_or("."));
    println!("{pad}flow {label}");
    for gate in state.gates.keys() {
        let status = gate_status(state, gate);
        let n_over = state.overrides.iter().filter(|o| o.gate == *gate).count();
        if n_over > 0 {
            println!("{pad}{gate}\t{status}\t⊘ {n_over}");
        } else {
            println!("{pad}{gate}\t{status}");
        }
    }
    if !state.overrides.is_empty() {
        println!("{pad}overrides");
        for o in &state.overrides {
            println!("{pad}  ⊘ {} ({}) — {}", o.check, o.gate, o.reason);
        }
    }
    if recursive && !state.children.is_empty() {
        println!("{pad}children");
        for child in &state.children {
            println!("{pad}- {child}");
            let child_dir = Path::new(child);
            let child_state = with_flow_lock(child_dir, || rebuild(child_dir))?;
            print_status(child_dir, &child_state, indent + 2, true)?;
        }
    }
    Ok(())
}

fn ready_gates(state: &State) -> Vec<String> {
    state
        .gates
        .keys()
        .filter(|gate| {
            let status = gate_status(state, gate);
            (status == GATE_PENDING || status == GATE_INVALIDATED || status == GATE_FAILED)
                && requirements_passed(state, gate)
        })
        .cloned()
        .collect()
}

fn gate_passed(state: &State, gate: &str) -> bool {
    gate_status(state, gate) == GATE_PASSED && requirements_passed(state, gate)
}

fn attempt_is_current(state: &State, id: &str) -> bool {
    let Some(attempt) = state.attempts.get(id) else {
        return false;
    };
    state
        .attempts
        .values()
        .filter(|other| other.gate == attempt.gate && other.kind == attempt.kind)
        .all(|other| other.seq <= attempt.seq)
}

fn requirements_passed(state: &State, gate: &str) -> bool {
    let Some(spec) = state.gates.get(gate) else {
        return false;
    };
    spec.requires
        .iter()
        .all(|required| gate_status(state, required) == GATE_PASSED)
}

fn gate_status(state: &State, gate: &str) -> String {
    if !state.gates.contains_key(gate) {
        return "missing".to_string();
    }
    state
        .gate_status
        .get(gate)
        .cloned()
        .unwrap_or_else(|| GATE_PENDING.to_string())
}

fn append_event(dir: &Path, event: &Event) -> Result<()> {
    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(events_path(dir))
        .map_err(|e| e.to_string())?;
    writeln!(file, "{}", render_event(event)).map_err(|e| e.to_string())
}

fn event(kind: &str, fields: Vec<(&str, Value)>) -> Event {
    Event {
        kind: kind.to_string(),
        fields: fields
            .into_iter()
            .map(|(key, value)| (key.to_string(), value))
            .collect(),
    }
}

fn render_event(event: &Event) -> String {
    serde_json::to_string(event).expect("flow events only contain serializable strings")
}

fn parse_event(line: &str) -> Result<Event> {
    serde_json::from_str(line).map_err(|err| format!("invalid event log line: {err}: {line}"))
}

impl Event {
    fn string(&self, key: &str) -> Option<String> {
        match self.fields.get(key) {
            Some(Value::String(value)) => Some(value.clone()),
            _ => None,
        }
    }

    fn required_string(&self, key: &str) -> Result<String> {
        self.string(key)
            .ok_or_else(|| format!("event {} missing string field {key}", self.kind))
    }

    fn array(&self, key: &str) -> Vec<String> {
        match self.fields.get(key) {
            Some(Value::Array(values)) => values.clone(),
            _ => Vec::new(),
        }
    }
}

fn parse_template_text(text: &str) -> Result<(Option<String>, Vec<GateSpec>)> {
    let template: FlowTemplate = toml::from_str(text).map_err(|e| e.to_string())?;

    let mut seen = BTreeSet::new();
    for gate in &template.gates {
        if gate.id.is_empty() {
            return Err("gate missing id".to_string());
        }
        if !seen.insert(gate.id.clone()) {
            return Err(format!("duplicate gate id: {}", gate.id));
        }
    }
    Ok((template.flow.and_then(|flow| flow.id), template.gates))
}

fn persist_flow_template(dir: &Path, template_text: &str) -> Result<()> {
    let path = dir.join(FLOW_TEMPLATE_FILE);
    fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    match fs::read_to_string(&path) {
        Ok(existing) if existing == template_text => Ok(()),
        Ok(_) => Err(format!(
            "{} already exists with different content",
            path.display()
        )),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            fs::write(path, template_text).map_err(|e| e.to_string())
        }
        Err(err) => Err(err.to_string()),
    }
}

// Absent file = no contract declared; flow runs no checks and passes attempts trivially.
fn load_protocol(dir: &Path) -> Result<Protocol> {
    let path = dir.join(PROTOCOL_FILE);
    if !path.exists() {
        return Ok(Protocol::default());
    }
    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    toml::from_str(&text).map_err(|e| format!("protocol.toml parse error: {e}"))
}

fn evaluate_gate(dir: &Path, state: &State, gate: &str) -> (String, Vec<CheckResult>) {
    let protocol = match load_protocol(dir) {
        Ok(p) => p,
        Err(e) => {
            return (
                GATE_FAILED.to_string(),
                vec![CheckResult {
                    id: "_protocol".to_string(),
                    pass: false,
                    detail: e,
                }],
            );
        }
    };
    let checks: Vec<&Check> = protocol.checks.iter().filter(|c| c.gate == gate).collect();
    if checks.is_empty() {
        return (GATE_PASSED.to_string(), vec![]);
    }
    let overridden: BTreeSet<&str> = state
        .overrides
        .iter()
        .map(|o| o.check.as_str())
        .collect();
    let mut results = Vec::new();
    let mut any_fail = false;
    for check in checks {
        if overridden.contains(check.id.as_str()) {
            results.push(CheckResult {
                id: check.id.clone(),
                pass: true,
                detail: "overridden".to_string(),
            });
            continue;
        }
        let r = eval_check(dir, state, check);
        if !r.pass {
            any_fail = true;
        }
        results.push(r);
    }
    let status = if any_fail { GATE_FAILED } else { GATE_PASSED };
    (status.to_string(), results)
}

fn eval_check(dir: &Path, state: &State, check: &Check) -> CheckResult {
    let r = match check.kind.as_str() {
        CHECK_AUDIT => eval_audit(state, check),
        CHECK_RUN => eval_run(dir, check),
        CHECK_EXISTS => eval_exists(dir, check),
        CHECK_AGREE => eval_agree(dir, check),
        CHECK_NEAR => eval_near(dir, check),
        CHECK_FRESH => eval_fresh(dir, check),
        other => (false, format!("unknown check kind: {other}")),
    };
    CheckResult {
        id: check.id.clone(),
        pass: r.0,
        detail: r.1,
    }
}

fn eval_audit(state: &State, check: &Check) -> (bool, String) {
    let producers: Vec<&Attempt> = state
        .attempts
        .values()
        .filter(|a| a.gate == check.gate && a.kind != CHECK_AUDIT && a.finished)
        .collect();
    let auditors: Vec<&Attempt> = state
        .attempts
        .values()
        .filter(|a| a.gate == check.gate && a.kind == CHECK_AUDIT && a.finished)
        .collect();
    if producers.is_empty() {
        return (false, "no producer attempt to audit".to_string());
    }
    if auditors.is_empty() {
        return (false, "no audit attempt finished".to_string());
    }
    for v in &auditors {
        if producers.iter().any(|p| p.actor == v.actor) {
            return (
                false,
                format!("self-audit: actor {} produced and audited", v.actor),
            );
        }
        if v.report.is_none() {
            return (false, format!("audit attempt {} has no report", v.actor));
        }
    }
    (true, format!("audited by {} actor(s)", auditors.len()))
}

fn eval_run(dir: &Path, check: &Check) -> (bool, String) {
    let Some(cmd) = check.cmd.as_ref() else {
        return (false, "run check missing cmd".to_string());
    };
    let output = Command::new("sh").arg("-c").arg(cmd).current_dir(dir).output();
    match output {
        Ok(o) if o.status.success() => (true, format!("exit 0: {}", cmd)),
        Ok(o) => (false, format!("exit {}: {}", o.status.code().unwrap_or(-1), cmd)),
        Err(e) => (false, format!("spawn failed: {e}")),
    }
}

fn eval_exists(dir: &Path, check: &Check) -> (bool, String) {
    let mut missing = Vec::new();
    for path in &check.paths {
        if !dir.join(path).exists() {
            missing.push(path.clone());
        }
    }
    for entry in &check.fields {
        // fields are "<path>:<dotted.field>"
        let Some((p, f)) = entry.split_once(':') else {
            missing.push(format!("malformed field {entry}"));
            continue;
        };
        let full = dir.join(p);
        if !full.exists() {
            missing.push(format!("{p} missing"));
            continue;
        }
        let value = read_json(&full).and_then(|v| pick(&v, f));
        if value.is_none() {
            missing.push(format!("{p}#{f}"));
        }
    }
    if missing.is_empty() {
        (true, format!("{} fields/paths present", check.paths.len() + check.fields.len()))
    } else {
        (false, format!("missing: {}", missing.join(", ")))
    }
}

fn eval_agree(dir: &Path, check: &Check) -> (bool, String) {
    if check.against.is_empty() {
        return (false, "agree check has no `against` entries".to_string());
    }
    // Each entry in `against` is "<path>:<dotted.field>"
    let mut values = Vec::new();
    for entry in &check.against {
        let Some((p, f)) = entry.split_once(':') else {
            return (false, format!("malformed: {entry}"));
        };
        let v = match read_json(&dir.join(p)).and_then(|v| pick(&v, f)) {
            Some(v) => v,
            None => return (false, format!("not readable: {entry}")),
        };
        values.push((entry.clone(), v));
    }
    let first = &values[0].1;
    for (entry, v) in &values[1..] {
        if v != first {
            return (false, format!("disagreement: {} vs {}", values[0].0, entry));
        }
    }
    (true, format!("{} sources agree", values.len()))
}

fn eval_near(dir: &Path, check: &Check) -> (bool, String) {
    if check.compare.is_empty() {
        return (false, "near check has no `compare` blocks".to_string());
    }
    let mut details = Vec::new();
    let mut any_fail = false;
    for c in &check.compare {
        let actual = read_json(&dir.join(&c.actual.path)).and_then(|v| pick_number(&v, &c.actual.field));
        let reference = read_json(&dir.join(&c.reference.path)).and_then(|v| pick_number(&v, &c.reference.field));
        let (Some(a), Some(r)) = (actual, reference) else {
            details.push("not readable".to_string());
            any_fail = true;
            continue;
        };
        let diff = (a - r).abs();
        let pass_abs = c.tolerance.abs.map(|t| diff <= t).unwrap_or(false);
        let pass_rel = c.tolerance.rel.map(|t| diff / r.abs().max(1e-30) <= t).unwrap_or(false);
        let pass_sigma = c
            .tolerance
            .sigma
            .and_then(|t| {
                c.uncertainty
                    .as_ref()
                    .and_then(|u| read_json(&dir.join(&u.path)).and_then(|v| pick_number(&v, &u.field)))
                    .map(|s| diff / s.abs().max(1e-30) <= t)
            })
            .unwrap_or(false);
        let ok = pass_abs || pass_rel || pass_sigma;
        if !ok {
            any_fail = true;
        }
        details.push(format!("|{a}-{r}|={diff:.3e}"));
    }
    (!any_fail, details.join("; "))
}

fn eval_fresh(dir: &Path, check: &Check) -> (bool, String) {
    if check.paths.is_empty() || check.against.is_empty() {
        return (false, "fresh check needs `paths` (artifacts) and `against` (sources)".to_string());
    }
    let oldest_artifact = check
        .paths
        .iter()
        .filter_map(|p| mtime(&dir.join(p)))
        .min();
    let newest_source = check
        .against
        .iter()
        .filter_map(|p| mtime(&dir.join(p)))
        .max();
    match (oldest_artifact, newest_source) {
        (Some(a), Some(s)) if a >= s => (true, "artifacts newer than sources".to_string()),
        (Some(_), Some(_)) => (false, "artifact older than a source".to_string()),
        _ => (false, "missing artifact or source mtime".to_string()),
    }
}

fn read_json(path: &Path) -> Option<serde_json::Value> {
    let text = fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn pick(value: &serde_json::Value, field: &str) -> Option<serde_json::Value> {
    let mut cur = value;
    for part in field.split('.') {
        cur = cur.get(part)?;
    }
    Some(cur.clone())
}

fn pick_number(value: &serde_json::Value, field: &str) -> Option<f64> {
    pick(value, field)?.as_f64()
}

fn mtime(path: &Path) -> Option<SystemTime> {
    fs::metadata(path).and_then(|m| m.modified()).ok()
}

fn write_state(dir: &Path, state: &State) -> Result<()> {
    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    let out = toml::to_string_pretty(&StateFile::from(state)).map_err(|e| e.to_string())?;
    fs::write(state_path(dir), out).map_err(|e| e.to_string())
}

#[derive(Serialize)]
struct StateFile {
    #[serde(skip_serializing_if = "Option::is_none")]
    flow: Option<StateFlow>,
    gates: BTreeMap<String, StateGate>,
    attempts: BTreeMap<String, StateAttempt>,
    artifacts: BTreeMap<String, StateArtifact>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    overrides: Vec<StateOverride>,
    children: StateChildren,
}

#[derive(Serialize)]
struct StateFlow {
    id: String,
}

#[derive(Serialize)]
struct StateGate {
    status: String,
    requires: Vec<String>,
    invalidates: Vec<String>,
}

#[derive(Serialize)]
struct StateAttempt {
    seq: u64,
    gate: String,
    kind: String,
    actor: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    executor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    command: Option<String>,
    finished: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    report: Option<String>,
}

#[derive(Serialize)]
struct StateArtifact {
    path: String,
    kind: String,
    hash: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    producer: Option<String>,
}

#[derive(Serialize)]
struct StateOverride {
    check: String,
    gate: String,
    reason: String,
    actor: String,
    at: String,
}

#[derive(Serialize)]
struct StateChildren {
    paths: Vec<String>,
}

impl From<&State> for StateFile {
    fn from(state: &State) -> Self {
        Self {
            flow: state
                .flow_id
                .as_ref()
                .map(|id| StateFlow { id: id.clone() }),
            gates: state
                .gates
                .iter()
                .map(|(id, gate)| {
                    (
                        id.clone(),
                        StateGate {
                            status: gate_status(state, id),
                            requires: gate.requires.clone(),
                            invalidates: gate.invalidates.clone(),
                        },
                    )
                })
                .collect(),
            attempts: state
                .attempts
                .iter()
                .map(|(id, attempt)| {
                    (
                        id.clone(),
                        StateAttempt {
                            seq: attempt.seq,
                            gate: attempt.gate.clone(),
                            kind: attempt.kind.clone(),
                            actor: attempt.actor.clone(),
                            executor: attempt.executor.clone(),
                            command: attempt.command.clone(),
                            finished: attempt.finished,
                            report: attempt.report.clone(),
                        },
                    )
                })
                .collect(),
            artifacts: state
                .artifacts
                .iter()
                .map(|(id, artifact)| {
                    (
                        id.clone(),
                        StateArtifact {
                            path: artifact.path.clone(),
                            kind: artifact.kind.clone(),
                            hash: artifact.hash.clone(),
                            producer: artifact.producer.clone(),
                        },
                    )
                })
                .collect(),
            overrides: state
                .overrides
                .iter()
                .map(|o| StateOverride {
                    check: o.check.clone(),
                    gate: o.gate.clone(),
                    reason: o.reason.clone(),
                    actor: o.actor.clone(),
                    at: o.at.clone(),
                })
                .collect(),
            children: StateChildren {
                paths: state.children.clone(),
            },
        }
    }
}

fn option_value(args: &[String], flag: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == flag)
        .map(|pair| pair[1].clone())
}

fn required_option(args: &[String], flag: &str) -> Result<String> {
    match option_value(args, flag) {
        Some(value) if value.starts_with("--") => Err(format!("{flag} requires a value")),
        Some(value) => Ok(value),
        None => Err(format!("missing {flag}")),
    }
}

fn option_list(args: &[String], flag: &str) -> Result<Vec<String>> {
    match option_value(args, flag) {
        Some(value) if value.trim().is_empty() => Ok(Vec::new()),
        Some(value) if value.starts_with("--") => Err(format!("{flag} requires a value")),
        Some(value) => Ok(value
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned)
            .collect()),
        None => Ok(Vec::new()),
    }
}

fn file_hash(path: &Path) -> Result<String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 8192];
    loop {
        let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(format!("sha256:{:x}", hasher.finalize()))
}

fn now_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{}-{nanos}", process::id())
}

fn flow_id_from_path(dir: &Path) -> String {
    dir.file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("flow")
        .to_string()
}

fn progress_dir(dir: &Path) -> PathBuf {
    dir.join("progress")
}

fn events_path(dir: &Path) -> PathBuf {
    progress_dir(dir).join("events.jsonl")
}

fn state_path(dir: &Path) -> PathBuf {
    progress_dir(dir).join("state.toml")
}

#[cfg(test)]
mod tests {
    use super::file_hash;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn file_hash_matches_known_vector() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("harness-flow-hash-{}-{nanos}", std::process::id()));
        fs::write(&path, b"abc").unwrap();
        assert_eq!(
            file_hash(&path).unwrap(),
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        fs::remove_file(path).unwrap();
    }
}
