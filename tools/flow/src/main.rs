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
const FLOW_TEMPLATE_FILE: &str = "flow.toml";
const PROTOCOL_FILE: &str = "protocol.toml";
const ACTOR_ENV: &str = "FLOW_ACTOR_ID";

// Identity is unforgeable-by-label: either host-injected via FLOW_ACTOR_ID,
// or derived from the parent process id. Different subagent processes get
// different PPIDs naturally; the same agent across calls keeps the same PPID.
fn current_identity() -> String {
    env::var(ACTOR_ENV)
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| format!("ppid:{}", std::os::unix::process::parent_id()))
}

// One-word generic check kinds. Each names what the check does, never what
// artifact it touches. Domain semantics live in protocol.toml fields.
const CHECK_AUDIT: &str = "audit"; // verifier ran with a distinct actor
const CHECK_RUN: &str = "run"; // external command exits zero
const CHECK_EXISTS: &str = "exists"; // declared fields/paths are present
const CHECK_AGREE: &str = "agree"; // declared values match across sources
const CHECK_NEAR: &str = "near"; // numeric within tolerance of reference
const CHECK_FRESH: &str = "fresh"; // artifact and declared sources unchanged since registration

// ─── State (read model) ──────────────────────────────────────────────────────

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
    actor_label: String,
    actor_identity: String,
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
    deps: BTreeMap<String, String>,
}

#[derive(Clone, Debug)]
struct Override {
    check: String,
    gate: String,
    reason: String,
    actor_label: String,
    actor_identity: String,
    at: String,
}

#[derive(Clone, Debug)]
struct Decision {
    id: String,
    question: String,
    choice: String,
    reason: Option<String>,
    actor_label: String,
    actor_identity: String,
    at: String,
}

#[derive(Clone, Debug)]
struct Deviation {
    id: String,
    statement: String,
    reason: Option<String>,
    actor_label: String,
    actor_identity: String,
    at: String,
}

#[derive(Debug, Default)]
struct State {
    seq: u64,
    flow_id: Option<String>,
    gates: BTreeMap<String, Gate>,
    attempts: BTreeMap<String, Attempt>,
    artifacts: BTreeMap<String, Artifact>,
    overrides: Vec<Override>,
    decisions: Vec<Decision>,
    deviations: Vec<Deviation>,
    children: Vec<String>,
}

// ─── Events (typed append-only log) ──────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "event")]
enum Event {
    #[serde(rename = "flow_initialized")]
    FlowInitialized {
        flow_id: String,
        created_at: String,
    },
    #[serde(rename = "gate_added")]
    GateAdded {
        id: String,
        #[serde(default)]
        requires: Vec<String>,
        #[serde(default)]
        invalidates: Vec<String>,
    },
    #[serde(rename = "attempt_started")]
    AttemptStarted {
        id: String,
        gate: String,
        kind: String,
        actor_label: String,
        actor_identity: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        executor: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        command: Option<String>,
    },
    #[serde(rename = "attempt_finished")]
    AttemptFinished {
        id: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        report: Option<String>,
    },
    #[serde(rename = "artifact_added")]
    ArtifactAdded {
        id: String,
        path: String,
        kind: String,
        hash: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        producer: Option<String>,
        #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
        deps: BTreeMap<String, String>,
    },
    #[serde(rename = "override_recorded")]
    OverrideRecorded {
        check: String,
        gate: String,
        reason: String,
        actor_label: String,
        actor_identity: String,
        at: String,
    },
    #[serde(rename = "decision_recorded")]
    DecisionRecorded {
        id: String,
        question: String,
        choice: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
        actor_label: String,
        actor_identity: String,
        at: String,
    },
    #[serde(rename = "deviation_recorded")]
    DeviationRecorded {
        id: String,
        statement: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
        actor_label: String,
        actor_identity: String,
        at: String,
    },
    #[serde(rename = "child_attached")]
    ChildAttached { path: String },
}

// ─── Protocol (the contract) ─────────────────────────────────────────────────

#[derive(Deserialize, Clone, Debug)]
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

#[derive(Deserialize, Clone, Debug, Default)]
struct ProtocolDeviation {
    #[serde(default)]
    id: String,
    #[serde(default)]
    statement: String,
    #[serde(default)]
    reason: String,
}

#[derive(Deserialize, Clone, Debug, Default)]
struct ProtocolPending {
    #[serde(default)]
    id: String,
    #[serde(default)]
    statement: String,
    #[serde(default)]
    reason: String,
}

#[derive(Deserialize, Default)]
struct Protocol {
    #[serde(default, rename = "checks")]
    checks: Vec<Check>,
    #[serde(default, rename = "deviations")]
    deviations: Vec<ProtocolDeviation>,
    #[serde(default, rename = "pending")]
    pending: Vec<ProtocolPending>,
}

#[derive(Clone, Debug)]
struct CheckResult {
    id: String,
    pass: bool,
    detail: String,
}

// ─── Entry ───────────────────────────────────────────────────────────────────

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
        "decide" => cmd_decide(&args),
        "deviate" => cmd_deviate(&args),
        "attach" => cmd_attach(&args),
        "help" | "--help" | "-h" => {
            println!("{}", usage());
            Ok(())
        }
        other => Err(format!("unknown command: {other}\n{}", usage())),
    }
}

fn usage() -> String {
    "usage: harness-flow <init|status|next|require|artifact|attempt|check|override|decide|deviate|attach> ..."
        .to_string()
}

// ─── init ────────────────────────────────────────────────────────────────────

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
            &Event::FlowInitialized {
                flow_id: flow_id.unwrap_or_else(|| flow_id_from_path(dir)),
                created_at: now_id(),
            },
        )?;
        for gate in gates {
            append_event(
                dir,
                &Event::GateAdded {
                    id: gate.id,
                    requires: gate.requires,
                    invalidates: gate.invalidates,
                },
            )?;
        }
        rebuild(dir)?;
        Ok(())
    })
}

// ─── status ──────────────────────────────────────────────────────────────────

fn cmd_status(args: &[String]) -> Result<()> {
    if args.is_empty() {
        return Err("usage: harness-flow status <dir> [--recursive]".to_string());
    }
    let dir = Path::new(&args[0]);
    let recursive = args.iter().skip(1).any(|arg| arg == "--recursive");
    let state = with_flow_lock(dir, || rebuild(dir))?;
    let protocol = load_protocol(dir)?;
    print_status(dir, &state, &protocol, 0, recursive)
}

fn print_status(
    dir: &Path,
    state: &State,
    protocol: &Protocol,
    indent: usize,
    recursive: bool,
) -> Result<()> {
    let pad = " ".repeat(indent);
    let label = state
        .flow_id
        .as_deref()
        .unwrap_or_else(|| dir.file_name().and_then(|v| v.to_str()).unwrap_or("."));
    println!("{pad}flow {label}");

    for gate in state.gates.keys() {
        let status = gate_status(dir, state, protocol, gate);
        let n_over = state.overrides.iter().filter(|o| o.gate == *gate).count();
        if n_over > 0 {
            println!("{pad}{gate}\t{status}\t⊘ {n_over}");
        } else {
            println!("{pad}{gate}\t{status}");
        }
    }

    let declared_deviations: Vec<&ProtocolDeviation> = protocol
        .deviations
        .iter()
        .filter(|d| !d.id.is_empty())
        .collect();
    let total_deviations = declared_deviations.len() + state.deviations.len();
    if total_deviations > 0 {
        println!("{pad}⚠ deviations ({total_deviations})");
        for d in &declared_deviations {
            print_deviation(&pad, &d.id, &d.statement, Some(&d.reason));
        }
        for d in &state.deviations {
            print_deviation(&pad, &d.id, &d.statement, d.reason.as_deref());
        }
    }

    if !state.overrides.is_empty() {
        println!("{pad}⊘ overrides ({})", state.overrides.len());
        for o in &state.overrides {
            println!("{pad}  ⊘ {} ({}) — {}", o.check, o.gate, o.reason);
        }
    }

    if !state.decisions.is_empty() {
        println!("{pad}decisions ({})", state.decisions.len());
        for d in &state.decisions {
            println!("{pad}  · {} — {} = {}", d.id, d.question, d.choice);
        }
    }

    let pending: Vec<&ProtocolPending> = protocol
        .pending
        .iter()
        .filter(|p| !p.id.is_empty())
        .collect();
    if !pending.is_empty() {
        println!("{pad}pending ({})", pending.len());
        for p in pending {
            if p.reason.is_empty() {
                println!("{pad}  · {} — {}", p.id, p.statement);
            } else {
                println!("{pad}  · {} — {} ({})", p.id, p.statement, p.reason);
            }
        }
    }

    let dir_arg = dir.display().to_string();
    let next: Vec<String> = ready_gates(dir, state, protocol);
    if !next.is_empty() {
        println!("{pad}next");
        for gate in next {
            println!("{pad}  flow attempt start {dir_arg} {gate} --kind <kind> --actor agent:<role>");
        }
    }

    if recursive && !state.children.is_empty() {
        println!("{pad}children");
        for child in &state.children {
            println!("{pad}- {child}");
            let child_dir = Path::new(child);
            let child_state = with_flow_lock(child_dir, || rebuild(child_dir))?;
            let child_protocol = load_protocol(child_dir)?;
            print_status(child_dir, &child_state, &child_protocol, indent + 2, true)?;
        }
    }
    Ok(())
}

// ─── next ────────────────────────────────────────────────────────────────────

fn cmd_next(args: &[String]) -> Result<()> {
    if args.len() != 1 {
        return Err("usage: harness-flow next <dir>".to_string());
    }
    let dir = Path::new(&args[0]);
    let dir_arg = &args[0];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    let protocol = load_protocol(dir)?;
    for gate in ready_gates(dir, &state, &protocol) {
        println!("{gate}");
        println!("  flow attempt start {dir_arg} {gate} --kind <kind> --actor agent:<role>");
    }
    Ok(())
}

// ─── require ─────────────────────────────────────────────────────────────────

fn cmd_require(args: &[String]) -> Result<()> {
    if args.len() != 2 {
        return Err("usage: harness-flow require <dir> <gate>".to_string());
    }
    let dir = Path::new(&args[0]);
    let gate = &args[1];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    let protocol = load_protocol(dir)?;
    if gate_passed(dir, &state, &protocol, gate) {
        Ok(())
    } else {
        Err(format!("{gate} not passed"))
    }
}

// ─── artifact ────────────────────────────────────────────────────────────────

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
    let rel = path
        .strip_prefix(dir)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| path.display().to_string());
    let deps = snapshot_deps(dir, &rel)?;
    with_flow_lock(dir, || {
        ensure_flow(dir)?;
        let state = rebuild(dir)?;
        if let Some(producer) = &producer {
            if !state.attempts.contains_key(producer) {
                return Err(format!("unknown producer attempt: {producer}"));
            }
        }
        append_event(
            dir,
            &Event::ArtifactAdded {
                id: id.clone(),
                path: rel,
                kind,
                hash,
                producer: producer.clone(),
                deps,
            },
        )?;
        rebuild(dir)?;
        Ok(())
    })
}

// ─── attempt ─────────────────────────────────────────────────────────────────

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
    let actor_label = required_option(args, "--actor")?;
    let actor_identity = current_identity();
    let executor = option_value(args, "--executor");
    let command = option_value(args, "--command");
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        let protocol = load_protocol(dir)?;
        if !state.gates.contains_key(&gate) {
            return Err(format!("unknown gate: {gate}"));
        }
        if !requirements_passed(dir, &state, &protocol, &gate) {
            return Err(format!("{gate} requirements not passed"));
        }
        let id = format!("a{}", now_id());
        append_event(
            dir,
            &Event::AttemptStarted {
                id: id.clone(),
                gate,
                kind,
                actor_label,
                actor_identity,
                executor,
                command,
            },
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
        append_event(
            dir,
            &Event::AttemptFinished {
                id: id.clone(),
                report,
            },
        )?;
        let state = rebuild(dir)?;
        let protocol = load_protocol(dir)?;
        let (status, results) = evaluate_gate(dir, &state, &protocol, &attempt.gate);
        for r in &results {
            let mark = if r.pass { "ok" } else { "fail" };
            println!("{mark}\t{}\t{}", r.id, r.detail);
        }
        println!("status\t{status}");
        Ok(())
    })
}

// ─── check ───────────────────────────────────────────────────────────────────

fn cmd_check(args: &[String]) -> Result<()> {
    if args.len() != 2 {
        return Err("usage: harness-flow check <dir> <gate>".to_string());
    }
    let dir = Path::new(&args[0]);
    let gate = &args[1];
    let state = with_flow_lock(dir, || rebuild(dir))?;
    let protocol = load_protocol(dir)?;
    if !state.gates.contains_key(gate) {
        return Err(format!("unknown gate: {gate}"));
    }
    let (status, results) = evaluate_gate(dir, &state, &protocol, gate);
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

// ─── override ────────────────────────────────────────────────────────────────

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
    let actor_label = option_value(args, "--actor").unwrap_or_else(|| "user".to_string());
    let actor_identity = current_identity();
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        let protocol = load_protocol(dir)?;
        let check = protocol
            .checks
            .iter()
            .find(|c| c.id == check_id)
            .ok_or_else(|| format!("unknown check: {check_id}"))?;
        if !state.gates.contains_key(&check.gate) {
            return Err(format!(
                "check {check_id} targets unknown gate {}",
                check.gate
            ));
        }
        append_event(
            dir,
            &Event::OverrideRecorded {
                check: check_id.clone(),
                gate: check.gate.clone(),
                reason,
                actor_label,
                actor_identity,
                at: now_id(),
            },
        )?;
        rebuild(dir)?;
        println!("override recorded: {check_id} (gate {})", check.gate);
        Ok(())
    })
}

// ─── decide ──────────────────────────────────────────────────────────────────

fn cmd_decide(args: &[String]) -> Result<()> {
    if args.len() < 7 {
        return Err(
            "usage: harness-flow decide <dir> --id <id> --question <text> --choice <text> [--reason <text>] [--actor <actor>]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[0]);
    let id = required_option(args, "--id")?;
    let question = required_option(args, "--question")?;
    let choice = required_option(args, "--choice")?;
    let reason = option_value(args, "--reason");
    let actor_label = option_value(args, "--actor").unwrap_or_else(|| "user".to_string());
    let actor_identity = current_identity();
    with_flow_lock(dir, || {
        ensure_flow(dir)?;
        append_event(
            dir,
            &Event::DecisionRecorded {
                id: id.clone(),
                question,
                choice,
                reason,
                actor_label,
                actor_identity,
                at: now_id(),
            },
        )?;
        rebuild(dir)?;
        println!("decision recorded: {id}");
        Ok(())
    })
}

// ─── deviate ─────────────────────────────────────────────────────────────────

fn cmd_deviate(args: &[String]) -> Result<()> {
    if args.len() < 5 {
        return Err(
            "usage: harness-flow deviate <dir> --id <id> --statement <text> [--reason <text>] [--actor <actor>]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[0]);
    let id = required_option(args, "--id")?;
    let statement = required_option(args, "--statement")?;
    let reason = option_value(args, "--reason");
    let actor_label = option_value(args, "--actor").unwrap_or_else(|| "user".to_string());
    let actor_identity = current_identity();
    with_flow_lock(dir, || {
        ensure_flow(dir)?;
        append_event(
            dir,
            &Event::DeviationRecorded {
                id: id.clone(),
                statement,
                reason,
                actor_label,
                actor_identity,
                at: now_id(),
            },
        )?;
        rebuild(dir)?;
        println!("deviation recorded: {id}");
        Ok(())
    })
}

// ─── attach ──────────────────────────────────────────────────────────────────

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
            &Event::ChildAttached {
                path: child.display().to_string(),
            },
        )?;
        rebuild(parent)?;
        Ok(())
    })
}

// ─── locks / paths ───────────────────────────────────────────────────────────

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

// ─── rebuild / persist ───────────────────────────────────────────────────────

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
    match event {
        Event::FlowInitialized { flow_id, .. } => {
            state.flow_id = Some(flow_id);
        }
        Event::GateAdded {
            id,
            requires,
            invalidates,
        } => {
            state.gates.insert(
                id,
                Gate {
                    requires,
                    invalidates,
                },
            );
        }
        Event::AttemptStarted {
            id,
            gate,
            kind,
            actor_label,
            actor_identity,
            executor,
            command,
        } => {
            state.attempts.insert(
                id,
                Attempt {
                    seq: event_seq,
                    gate,
                    kind,
                    actor_label,
                    actor_identity,
                    executor,
                    command,
                    report: None,
                    finished: false,
                },
            );
        }
        Event::AttemptFinished { id, report } => {
            let attempt = state
                .attempts
                .get_mut(&id)
                .ok_or_else(|| format!("unknown attempt in event log: {id}"))?;
            attempt.finished = true;
            attempt.report = report;
        }
        Event::ArtifactAdded {
            id,
            path,
            kind,
            hash,
            producer,
            deps,
        } => {
            state.artifacts.insert(
                id,
                Artifact {
                    path,
                    kind,
                    producer,
                    hash,
                    deps,
                },
            );
        }
        Event::OverrideRecorded {
            check,
            gate,
            reason,
            actor_label,
            actor_identity,
            at,
        } => {
            state.overrides.push(Override {
                check,
                gate,
                reason,
                actor_label,
                actor_identity,
                at,
            });
        }
        Event::DecisionRecorded {
            id,
            question,
            choice,
            reason,
            actor_label,
            actor_identity,
            at,
        } => {
            state.decisions.push(Decision {
                id,
                question,
                choice,
                reason,
                actor_label,
                actor_identity,
                at,
            });
        }
        Event::DeviationRecorded {
            id,
            statement,
            reason,
            actor_label,
            actor_identity,
            at,
        } => {
            state.deviations.push(Deviation {
                id,
                statement,
                reason,
                actor_label,
                actor_identity,
                at,
            });
        }
        Event::ChildAttached { path } => {
            state.children.push(path);
        }
    }
    Ok(())
}

fn append_event(dir: &Path, event: &Event) -> Result<()> {
    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(events_path(dir))
        .map_err(|e| e.to_string())?;
    let line = serde_json::to_string(event).map_err(|e| e.to_string())?;
    writeln!(file, "{line}").map_err(|e| e.to_string())
}

fn parse_event(line: &str) -> Result<Event> {
    serde_json::from_str(line).map_err(|err| format!("invalid event log line: {err}: {line}"))
}

// ─── template / protocol parsing ─────────────────────────────────────────────

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

// ─── gate evaluation (derived status) ────────────────────────────────────────

fn evaluate_gate(
    dir: &Path,
    state: &State,
    protocol: &Protocol,
    gate: &str,
) -> (String, Vec<CheckResult>) {
    let checks: Vec<&Check> = protocol.checks.iter().filter(|c| c.gate == gate).collect();
    if checks.is_empty() {
        // No checks declared: passed once any attempt finished, else pending.
        let any_finished = state
            .attempts
            .values()
            .any(|a| a.gate == gate && a.finished);
        let status = if any_finished {
            GATE_PASSED
        } else {
            GATE_PENDING
        };
        return (status.to_string(), vec![]);
    }
    let overridden: BTreeSet<&str> = state.overrides.iter().map(|o| o.check.as_str()).collect();
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
        CHECK_FRESH => eval_fresh(dir, state, check),
        other => (false, format!("unknown check kind: {other}")),
    };
    CheckResult {
        id: check.id.clone(),
        pass: r.0,
        detail: r.1,
    }
}

// Producer and auditor must be distinct actors. Identity (env-stamped) wins
// over label; matching identity is a hard self-audit. If either side lacks
// identity, label comparison is the fallback with an explicit note.
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
        if v.report.is_none() {
            return (
                false,
                format!("audit attempt {} has no report", v.actor_label),
            );
        }
        for p in &producers {
            if p.actor_identity == v.actor_identity {
                return (
                    false,
                    format!(
                        "self-audit: identity {} produced and audited",
                        v.actor_identity
                    ),
                );
            }
        }
    }
    (true, format!("audited by {} distinct actor(s)", auditors.len()))
}

fn eval_run(dir: &Path, check: &Check) -> (bool, String) {
    let Some(cmd) = check.cmd.as_ref() else {
        return (false, "run check missing cmd".to_string());
    };
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .current_dir(dir)
        .output();
    match output {
        Ok(o) if o.status.success() => (true, format!("exit 0: {}", cmd)),
        Ok(o) => (
            false,
            format!("exit {}: {}", o.status.code().unwrap_or(-1), cmd),
        ),
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
    for field in &check.fields {
        let (file, key) = match field.split_once(':') {
            Some((f, k)) => (f, k),
            None => {
                missing.push(format!("{field} (malformed; expected path:field)"));
                continue;
            }
        };
        let json = match read_json(&dir.join(file)) {
            Some(v) => v,
            None => {
                missing.push(format!("{file}:{key} (file missing or not json)"));
                continue;
            }
        };
        if pick(&json, key).is_none() {
            missing.push(format!("{file}:{key}"));
        }
    }
    if missing.is_empty() {
        let n = check.paths.len() + check.fields.len();
        (true, format!("{n} declared paths/fields present"))
    } else {
        (false, format!("missing: {}", missing.join(", ")))
    }
}

fn eval_agree(dir: &Path, check: &Check) -> (bool, String) {
    if check.against.len() < 2 {
        return (
            false,
            "agree check needs at least two `against` entries (path:field each)".to_string(),
        );
    }
    let mut values: Vec<(String, serde_json::Value)> = Vec::new();
    for entry in &check.against {
        let (file, key) = match entry.split_once(':') {
            Some(pair) => pair,
            None => return (false, format!("malformed against entry: {entry}")),
        };
        let json = match read_json(&dir.join(file)) {
            Some(v) => v,
            None => return (false, format!("cannot read {file}")),
        };
        let value = match pick(&json, key) {
            Some(v) => v,
            None => return (false, format!("missing {file}:{key}")),
        };
        values.push((entry.clone(), value));
    }
    let head = &values[0].1;
    for (label, value) in values.iter().skip(1) {
        if value != head {
            return (
                false,
                format!("{} differs from {}", label, values[0].0),
            );
        }
    }
    (true, format!("{} entries agree", values.len()))
}

fn eval_near(dir: &Path, check: &Check) -> (bool, String) {
    if check.compare.is_empty() {
        return (false, "near check needs [[checks.compare]] entries".to_string());
    }
    let mut details = Vec::new();
    let mut any_fail = false;
    for c in &check.compare {
        let a_path = dir.join(&c.actual.path);
        let r_path = dir.join(&c.reference.path);
        let a = match read_json(&a_path).and_then(|v| pick_number(&v, &c.actual.field)) {
            Some(v) => v,
            None => {
                any_fail = true;
                details.push(format!("missing actual {}:{}", c.actual.path, c.actual.field));
                continue;
            }
        };
        let r = match read_json(&r_path).and_then(|v| pick_number(&v, &c.reference.field)) {
            Some(v) => v,
            None => {
                any_fail = true;
                details.push(format!(
                    "missing reference {}:{}",
                    c.reference.path, c.reference.field
                ));
                continue;
            }
        };
        let diff = (a - r).abs();
        let pass_abs = c.tolerance.abs.map(|t| diff <= t).unwrap_or(false);
        let pass_rel = c
            .tolerance
            .rel
            .map(|t| diff / r.abs().max(1e-30) <= t)
            .unwrap_or(false);
        let pass_sigma = c
            .tolerance
            .sigma
            .map(|t| {
                c.uncertainty
                    .as_ref()
                    .and_then(|u| read_json(&dir.join(&u.path)).and_then(|v| pick_number(&v, &u.field)))
                    .map(|s| diff / s.abs().max(1e-30) <= t)
                    .unwrap_or(false)
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

fn eval_fresh(dir: &Path, state: &State, check: &Check) -> (bool, String) {
    if check.paths.is_empty() || check.against.is_empty() {
        return (
            false,
            "fresh check needs `paths` (artifacts) and `against` (sources)".to_string(),
        );
    }
    for path in &check.paths {
        let artifact = match state.artifacts.values().find(|a| a.path == *path) {
            Some(a) => a,
            None => return (false, format!("no artifact registered for {path}")),
        };
        match file_hash(&dir.join(path)) {
            Ok(h) if h == artifact.hash => {}
            Ok(_) => return (false, format!("artifact mutated since registration: {path}")),
            Err(e) => return (false, format!("cannot hash artifact {path}: {e}")),
        }
        for source in &check.against {
            let registered = match artifact.deps.get(source) {
                Some(h) => h,
                None => {
                    return (
                        false,
                        format!("no snapshot of {source} for {path}; re-register the artifact"),
                    )
                }
            };
            match file_hash(&dir.join(source)) {
                Ok(h) if h == *registered => {}
                Ok(_) => return (false, format!("source changed since registration: {source}")),
                Err(e) => return (false, format!("cannot hash source {source}: {e}")),
            }
        }
    }
    (
        true,
        format!("{} artifact(s) and sources unchanged", check.paths.len()),
    )
}

fn snapshot_deps(dir: &Path, artifact_path: &str) -> Result<BTreeMap<String, String>> {
    let protocol = load_protocol(dir)?;
    let mut deps = BTreeMap::new();
    for check in &protocol.checks {
        if check.kind != CHECK_FRESH {
            continue;
        }
        if !check.paths.iter().any(|p| p == artifact_path) {
            continue;
        }
        for source in &check.against {
            if deps.contains_key(source) {
                continue;
            }
            let resolved = dir.join(source);
            if !resolved.exists() {
                return Err(format!(
                    "fresh-check source missing at registration of {artifact_path}: {source}"
                ));
            }
            deps.insert(source.clone(), file_hash(&resolved)?);
        }
    }
    Ok(deps)
}

// ─── derived queries ─────────────────────────────────────────────────────────

fn gate_status(dir: &Path, state: &State, protocol: &Protocol, gate: &str) -> String {
    if !state.gates.contains_key(gate) {
        return "missing".to_string();
    }
    evaluate_gate(dir, state, protocol, gate).0
}

fn gate_passed(dir: &Path, state: &State, protocol: &Protocol, gate: &str) -> bool {
    gate_status(dir, state, protocol, gate) == GATE_PASSED
        && requirements_passed(dir, state, protocol, gate)
}

fn requirements_passed(dir: &Path, state: &State, protocol: &Protocol, gate: &str) -> bool {
    let Some(spec) = state.gates.get(gate) else {
        return false;
    };
    spec.requires
        .iter()
        .all(|required| gate_status(dir, state, protocol, required) == GATE_PASSED)
}

fn print_deviation(pad: &str, id: &str, statement: &str, reason: Option<&str>) {
    let trimmed = reason.map(str::trim).filter(|r| !r.is_empty());
    if let Some(r) = trimmed {
        println!("{pad}  ⚠ {id} — {statement} ({r})");
    } else {
        println!("{pad}  ⚠ {id} — {statement}");
    }
}

fn ready_gates(dir: &Path, state: &State, protocol: &Protocol) -> Vec<String> {
    state
        .gates
        .keys()
        .filter(|gate| {
            let status = gate_status(dir, state, protocol, gate);
            status != GATE_PASSED && requirements_passed(dir, state, protocol, gate)
        })
        .cloned()
        .collect()
}

// ─── option parsing ──────────────────────────────────────────────────────────

fn option_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn required_option(args: &[String], flag: &str) -> Result<String> {
    option_value(args, flag).ok_or_else(|| format!("missing {flag}"))
}

// ─── json helpers ────────────────────────────────────────────────────────────

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

// ─── state.toml projection ───────────────────────────────────────────────────

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
    overrides: Vec<StateRecord>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    decisions: Vec<StateDecision>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    deviations: Vec<StateDeviation>,
    children: StateChildren,
}

#[derive(Serialize)]
struct StateFlow {
    id: String,
}

#[derive(Serialize)]
struct StateGate {
    requires: Vec<String>,
    invalidates: Vec<String>,
}

#[derive(Serialize)]
struct StateAttempt {
    seq: u64,
    gate: String,
    kind: String,
    actor_label: String,
    actor_identity: String,
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
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    deps: BTreeMap<String, String>,
}

#[derive(Serialize)]
struct StateRecord {
    check: String,
    gate: String,
    reason: String,
    actor_label: String,
    actor_identity: String,
    at: String,
}

#[derive(Serialize)]
struct StateDecision {
    id: String,
    question: String,
    choice: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<String>,
    actor_label: String,
    actor_identity: String,
    at: String,
}

#[derive(Serialize)]
struct StateDeviation {
    id: String,
    statement: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<String>,
    actor_label: String,
    actor_identity: String,
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
                            actor_label: attempt.actor_label.clone(),
                            actor_identity: attempt.actor_identity.clone(),
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
                            deps: artifact.deps.clone(),
                        },
                    )
                })
                .collect(),
            overrides: state
                .overrides
                .iter()
                .map(|o| StateRecord {
                    check: o.check.clone(),
                    gate: o.gate.clone(),
                    reason: o.reason.clone(),
                    actor_label: o.actor_label.clone(),
                    actor_identity: o.actor_identity.clone(),
                    at: o.at.clone(),
                })
                .collect(),
            decisions: state
                .decisions
                .iter()
                .map(|d| StateDecision {
                    id: d.id.clone(),
                    question: d.question.clone(),
                    choice: d.choice.clone(),
                    reason: d.reason.clone(),
                    actor_label: d.actor_label.clone(),
                    actor_identity: d.actor_identity.clone(),
                    at: d.at.clone(),
                })
                .collect(),
            deviations: state
                .deviations
                .iter()
                .map(|d| StateDeviation {
                    id: d.id.clone(),
                    statement: d.statement.clone(),
                    reason: d.reason.clone(),
                    actor_label: d.actor_label.clone(),
                    actor_identity: d.actor_identity.clone(),
                    at: d.at.clone(),
                })
                .collect(),
            children: StateChildren {
                paths: state.children.clone(),
            },
        }
    }
}

// ─── misc ────────────────────────────────────────────────────────────────────

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
