use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process;
use std::thread;
use std::time::Duration;
use std::time::Instant;
use std::time::{SystemTime, UNIX_EPOCH};

type Result<T> = std::result::Result<T, String>;

const GATE_PENDING: &str = "pending";
const GATE_PASSED: &str = "passed";
const GATE_FAILED: &str = "failed";
const GATE_BLOCKED: &str = "blocked";
const GATE_INVALIDATED: &str = "invalidated";
const ATTEMPT_PASS: &str = "pass";
const ATTEMPT_FAIL: &str = "fail";
const ATTEMPT_BLOCKED: &str = "blocked";

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
    status: Option<String>,
    report: Option<String>,
}

#[derive(Clone, Debug)]
struct Artifact {
    path: String,
    kind: String,
    producer: Option<String>,
    hash: String,
}

#[derive(Debug, Default)]
struct State {
    seq: u64,
    flow_id: Option<String>,
    gates: BTreeMap<String, Gate>,
    gate_status: BTreeMap<String, String>,
    attempts: BTreeMap<String, Attempt>,
    artifacts: BTreeMap<String, Artifact>,
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
        "gate" => cmd_gate(&args),
        "artifact" => cmd_artifact(&args),
        "attempt" => cmd_attempt(&args),
        "invalidate" => cmd_invalidate(&args),
        "attach" => cmd_attach(&args),
        "rebuild" => cmd_rebuild(&args),
        "-h" | "--help" | "help" => {
            println!("{}", usage());
            Ok(())
        }
        other => Err(format!("unknown command: {other}\n{}", usage())),
    }
}

fn usage() -> String {
    "usage: harness-flow <init|status|next|require|gate|artifact|attempt|invalidate|attach|rebuild> ..."
        .to_string()
}

fn cmd_init(args: &[String]) -> Result<()> {
    if args.len() != 3 || args[1] != "--template" {
        return Err("usage: harness-flow init <dir> --template <template.toml>".to_string());
    }
    let dir = Path::new(&args[0]);
    let template = Path::new(&args[2]);
    let (flow_id, gates) = parse_template(template)?;

    fs::create_dir_all(progress_dir(dir)).map_err(|e| e.to_string())?;
    with_flow_lock(dir, || {
        let events = events_path(dir);
        if events.exists() {
            return Err(format!("flow already exists: {}", dir.display()));
        }

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
    let state = with_flow_lock(dir, || rebuild(dir))?;
    for gate in ready_gates(&state) {
        println!("{gate}");
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

fn cmd_gate(args: &[String]) -> Result<()> {
    if args.len() < 3 || args[0] != "add" {
        return Err(
            "usage: harness-flow gate add <dir> <gate> [--requires a,b] [--invalidates x,y]"
                .to_string(),
        );
    }
    let dir = Path::new(&args[1]);
    let id = args[2].clone();
    let requires = option_list(args, "--requires")?;
    let invalidates = option_list(args, "--invalidates")?;
    with_flow_lock(dir, || {
        ensure_flow(dir)?;
        append_event(
            dir,
            &event(
                "gate_added",
                vec![
                    ("id", Value::String(id)),
                    ("requires", Value::Array(requires)),
                    ("invalidates", Value::Array(invalidates)),
                ],
            ),
        )?;
        rebuild(dir)?;
        Ok(())
    })
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
    if args.len() < 7 {
        return Err(
            "usage: harness-flow attempt finish <dir> <attempt> --status pass|fail|blocked --report <path>"
                .to_string(),
        );
    }
    let dir = Path::new(&args[1]);
    let id = args[2].clone();
    let status = required_option(args, "--status")?;
    if !matches!(
        status.as_str(),
        ATTEMPT_PASS | ATTEMPT_FAIL | ATTEMPT_BLOCKED
    ) {
        return Err("status must be pass, fail, or blocked".to_string());
    }
    let report = required_option(args, "--report")?;
    if !Path::new(&report).exists() {
        return Err(format!("report not found: {report}"));
    }
    with_flow_lock(dir, || {
        let state = rebuild(dir)?;
        if !state.attempts.contains_key(&id) {
            return Err(format!("unknown attempt: {id}"));
        }
        if state
            .attempts
            .get(&id)
            .and_then(|attempt| attempt.status.as_ref())
            .is_some()
        {
            return Err(format!("attempt already finished: {id}"));
        }
        if !attempt_is_current(&state, &id) {
            return Err(format!("stale attempt: {id}"));
        }

        append_event(
            dir,
            &event(
                "attempt_finished",
                vec![
                    ("id", Value::String(id)),
                    ("status", Value::String(status)),
                    ("report", Value::String(report)),
                ],
            ),
        )?;
        rebuild(dir)?;
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

fn cmd_rebuild(args: &[String]) -> Result<()> {
    if args.len() != 1 {
        return Err("usage: harness-flow rebuild <dir>".to_string());
    }
    let dir = Path::new(&args[0]);
    with_flow_lock(dir, || {
        rebuild(dir)?;
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
                    status: None,
                    report: None,
                },
            );
        }
        "attempt_finished" => {
            let id = event.required_string("id")?;
            let status = event.required_string("status")?;
            let report = event.required_string("report")?;
            let attempt_view = state
                .attempts
                .get(&id)
                .ok_or_else(|| format!("unknown attempt in event log: {id}"))?;
            let gate = attempt_view.gate.clone();
            let is_current = attempt_is_current(state, &id);
            let attempt = state
                .attempts
                .get_mut(&id)
                .ok_or_else(|| format!("unknown attempt in event log: {id}"))?;
            attempt.status = Some(status.clone());
            attempt.report = Some(report);
            if !is_current {
                return Ok(());
            }
            let gate_status = match status.as_str() {
                ATTEMPT_PASS => GATE_PASSED,
                ATTEMPT_FAIL => GATE_FAILED,
                ATTEMPT_BLOCKED => GATE_BLOCKED,
                _ => return Err(format!("invalid attempt status in event log: {status}")),
            };
            state.gate_status.insert(gate, gate_status.to_string());
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
        println!("{pad}{gate}\t{status}");
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
            (status == GATE_PENDING || status == GATE_INVALIDATED)
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
        .filter(|other| other.gate == attempt.gate)
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

fn parse_template(path: &Path) -> Result<(Option<String>, Vec<GateSpec>)> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let template: FlowTemplate = toml::from_str(&text).map_err(|e| e.to_string())?;

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
    #[serde(skip_serializing_if = "Option::is_none")]
    status: Option<String>,
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
                            status: attempt.status.clone(),
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
