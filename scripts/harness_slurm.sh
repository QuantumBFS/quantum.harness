#!/usr/bin/env bash
# harness_slurm.sh — mechanical driver for the /using-slurm skill.
#
# Factors the deterministic ssh/sbatch/squeue/sacct mechanics out of the agent:
# resolve the cluster profile, run pre-checks, probe partitions, submit an array
# job, poll status, fetch results, classify per-cell outcomes, and list cells
# that still need to run. The skill keeps the JUDGMENT (which partition, whether
# to ship a dirty tree, whether to retry a failed cell); this script only
# performs the fixed operations and parses their output.
#
# It hard-codes NO cluster specifics. Connection details come from the active
# cluster profile (skills/using-slurm/profiles/active.toml or
# $HARNESS_CLUSTER_PROFILE) or from explicit overrides:
#   --alias / $HARNESS_SSH_ALIAS         ssh handle (wins over the profile)
#   --repo  / $HARNESS_REPO_REMOTE       remote repo checkout path
#   --profile <file>                     use this profile instead of active.md
# Set HARNESS_SLURM_DRYRUN=1 to print every remote command instead of running
# it (useful for previewing a submission before it leaves the laptop).
#
# Subcommands:
#   precheck                 resolve profile, test ssh, capture git dirty status
#   probe-partitions         ssh sinfo and print a parsed candidate table
#   submit ...               build+run sbatch, capture the job id (see --help)
#   status <jobid>           squeue the job, parse state + pending-reason category
#   fetch <run>              rsync results/<run>/ back from the cluster
#   classify <run> <jobid>   sacct + per-cell manifests -> cell outcome table
#   pending-cells <run>      list planned cells lacking a success-tagged manifest
#
# Pure helpers (read stdin; used internally, exposed for testing):
#   parse-sinfo              normalize `sinfo -o "%P %a %.10l %.6D %.6t"`
#   parse-sacct              normalize `sacct ... -P` into cell-joinable rows
#   classify-reason <reason> map a squeue pending reason to a category

set -euo pipefail

PROFILE_DEFAULT="skills/using-slurm/profiles/active.toml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SINFO_FMT='%P %a %.10l %.6D %.6t'
SACCT_FMT='JobID,State,ExitCode,MaxRSS,Elapsed'

die() { echo "harness_slurm: $*" >&2; exit 1; }

# --- profile / connection resolution ----------------------------------------

profile_path() {
  if [[ -n "${HARNESS_PROFILE_FILE:-}" ]]; then echo "$HARNESS_PROFILE_FILE"; return; fi
  if [[ -n "${HARNESS_CLUSTER_PROFILE:-}" ]]; then
    echo "skills/using-slurm/profiles/${HARNESS_CLUSTER_PROFILE}.toml"; return
  fi
  echo "$PROFILE_DEFAULT"
}

# Read a dotted field (e.g. `connection.ssh.alias`) out of the TOML profile.
# Parsing lives in Python (cluster_profile.py) — bash stays mechanics-only and
# never parses TOML itself. Returns non-zero if the field is unset/file absent.
profile_field() {
  local field="$1" file="$2"
  [[ -f "$file" ]] || return 1
  python3 "$SCRIPT_DIR/cluster_profile.py" --field "$field" --profile "$file" 2>/dev/null
}

resolve_alias() {
  if [[ -n "${HARNESS_SSH_ALIAS:-}" ]]; then echo "$HARNESS_SSH_ALIAS"; return; fi
  local v; v="$(profile_field 'connection.ssh.alias' "$(profile_path)" || true)"
  [[ -n "$v" ]] || die "no ssh alias: set --alias, \$HARNESS_SSH_ALIAS, or connection.ssh.alias in $(profile_path)"
  echo "$v"
}

resolve_repo() {
  if [[ -n "${HARNESS_REPO_REMOTE:-}" ]]; then echo "$HARNESS_REPO_REMOTE"; return; fi
  local v; v="$(profile_field 'connection.repo_path_remote' "$(profile_path)" || true)"
  [[ -n "$v" ]] || die "no remote repo path: set --repo, \$HARNESS_REPO_REMOTE, or connection.repo_path_remote in $(profile_path)"
  echo "$v"
}

# Whether to wrap remote commands in a login shell. Some clusters expose the
# scheduler (sbatch/squeue/sinfo) only on the login-shell PATH (sourced from
# /etc/profile / modules), which non-interactive ssh skips. Cluster-agnostic:
# off unless connection.login_shell=true in the profile (or $HARNESS_LOGIN_SHELL).
login_shell_enabled() {
  if [[ -n "${HARNESS_LOGIN_SHELL:-}" ]]; then
    [[ "$HARNESS_LOGIN_SHELL" == "1" || "$HARNESS_LOGIN_SHELL" == "true" ]]
    return
  fi
  local v; v="$(profile_field 'connection.login_shell' "$(profile_path)" || true)"
  [[ "$v" == "true" || "$v" == "1" ]]
}

# Run a command on the cluster (or print it under dry-run).
remote() {
  local alias="$1"; shift
  local cmd="$*"
  if login_shell_enabled; then
    local esc=${cmd//\'/\'\\\'\'}   # single-quote-safe for the remote shell
    cmd="bash -lc '$esc'"
  fi
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then
    echo "DRYRUN ssh $alias $cmd" >&2
    return 0
  fi
  ssh -o BatchMode=yes "$alias" "$cmd"
}

# --- pure parsers (testable from stdin) --------------------------------------

# Normalize sinfo output to: partition avail timelimit nodes state
parse_sinfo() {
  awk 'NR==1 && $1 ~ /PARTITION/ {next}
       NF>=5 {printf "%s\t%s\t%s\t%s\t%s\n", $1, $2, $3, $4, $5}'
}

# Normalize `sacct --format=JobID,State,ExitCode,MaxRSS,Elapsed -P` (pipe-sep).
# Emits one row per array task (JobID like 12345_3), dropping .batch/.extern
# sub-steps: arraytask<TAB>state<TAB>exitcode<TAB>maxrss<TAB>elapsed
parse_sacct() {
  awk -F'|' 'NR==1 && $1=="JobID" {next}
             $1 ~ /^[0-9]+_[0-9]+$/ {
               split($1, a, "_");
               printf "%s\t%s\t%s\t%s\t%s\n", a[2], $2, $3, $4, $5
             }'
}

# Map a squeue pending reason to an action category.
classify_reason() {
  case "$1" in
    Priority|Resources|BeginTime|Reservation|None|"")
      echo "queued" ;;
    AssocMaxJobsLimit|QOSMaxJobsPerUserLimit|AssocGrpCPULimit|QOSMaxCpuPerUserLimit|*Limit)
      echo "throttle" ;;
    Dependency|DependencyNeverSatisfied)
      echo "dependency" ;;
    *)
      echo "other" ;;
  esac
}

# Map a sacct State + ExitCode to an outcome classification.
classify_state() {
  local state="$1" exit_code="$2"
  case "$state" in
    COMPLETED) echo "success" ;;
    OUT_OF_ME*|OOM*) echo "oom" ;;
    TIMEOUT) echo "walltime" ;;
    FAILED) [[ "$exit_code" == "0:0" ]] && echo "logic-failure" || echo "nonzero-exit" ;;
    CANCELLED*) echo "cancelled" ;;
    RUNNING|PENDING|REQUEUED) echo "in-progress" ;;
    *) echo "unknown:$state" ;;
  esac
}

# --- subcommands -------------------------------------------------------------

cmd_precheck() {
  local alias repo
  alias="$(resolve_alias)"; repo="$(resolve_repo)"
  local ssh_ok="false"
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then
    ssh_ok="dryrun"
  elif ssh -o BatchMode=yes -o ConnectTimeout=10 "$alias" 'echo ok' 2>/dev/null | grep -q ok; then
    ssh_ok="true"
  fi
  local dirty; dirty="$(git status --porcelain 2>/dev/null || true)"
  local n_dirty; n_dirty="$(printf '%s' "$dirty" | grep -c . || true)"
  echo "profile:   $(profile_path)"
  echo "alias:     $alias"
  echo "repo:      $repo"
  echo "ssh_ok:    $ssh_ok"
  echo "dirty:     ${n_dirty} file(s)"
  [[ "$n_dirty" -gt 0 ]] && printf '%s\n' "$dirty" | sed 's/^/  /'
  [[ "$ssh_ok" == "true" || "$ssh_ok" == "dryrun" ]] || die "ssh to '$alias' failed; check ~/.ssh/config and the profile"
}

cmd_probe_partitions() {
  local alias; alias="$(resolve_alias)"
  echo -e "PARTITION\tAVAIL\tTIMELIMIT\tNODES\tSTATE"
  remote "$alias" "sinfo -o '$SINFO_FMT'" | parse_sinfo
}

cmd_submit() {
  local array="" run_spec="" command="" entrypoint="" partition="" walltime="" cpus="" \
        script="scripts/harness_array_sbatch.sh" extra=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --array) array="$2"; shift 2 ;;
      --run-spec) run_spec="$2"; shift 2 ;;
      --command) command="$2"; shift 2 ;;
      --entrypoint) entrypoint="$2"; shift 2 ;;
      --partition) partition="$2"; shift 2 ;;
      --time) walltime="$2"; shift 2 ;;
      --cpus) cpus="$2"; shift 2 ;;
      --script) script="$2"; shift 2 ;;
      --extra) extra="$2"; shift 2 ;;
      *) die "submit: unknown flag $1" ;;
    esac
  done
  [[ -n "$script" ]] || die "submit: --script is required"
  # Two paths: a harness array/run-spec job, or a plain single-script job
  # (the /cluster-jobs student case). The array contract injects HARNESS_*;
  # a plain job just ships the script with the resource flags.
  local exports="ALL"
  if [[ -n "$run_spec" ]]; then
    [[ -n "$command" || -n "$entrypoint" ]] || die "submit: --command or --entrypoint is required with --run-spec"
    exports="ALL,HARNESS_RUN_SPEC=${run_spec}"
    [[ -n "$command" ]] && exports="${exports},HARNESS_COMMAND=${command}"
    [[ -n "$entrypoint" ]] && exports="${exports},HARNESS_ENTRYPOINT=${entrypoint}"
  elif [[ -n "$array" ]]; then
    die "submit: --array requires --run-spec; use a plain --script for single jobs"
  fi
  local alias repo; alias="$(resolve_alias)"; repo="$(resolve_repo)"

  local sbatch="sbatch"
  [[ -n "$partition" ]] && sbatch="$sbatch --partition=$partition"
  [[ -n "$walltime" ]]  && sbatch="$sbatch --time=$walltime"
  [[ -n "$cpus" ]]      && sbatch="$sbatch --cpus-per-task=$cpus"
  [[ -n "$array" ]]     && sbatch="$sbatch --array=1-$array"
  [[ -n "$extra" ]]     && sbatch="$sbatch $extra"
  sbatch="$sbatch --export=$exports $script"

  local out
  out="$(remote "$alias" "cd $repo && $sbatch")"
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then return 0; fi
  local jobid; jobid="$(printf '%s' "$out" | grep -oE 'Submitted batch job [0-9]+' | awk '{print $NF}')"
  [[ -n "$jobid" ]] || { printf '%s\n' "$out" >&2; die "could not parse a job id from sbatch output"; }
  echo "job_id:    $jobid"
  echo "partition: ${partition:-<profile-default>}"
  echo "walltime:  ${walltime:-<profile-default>}"
  echo "n_cells:   ${array:-1}"
  echo "script:    $script"
}

cmd_status() {
  local jobid="${1:?status: <jobid> required}"
  local alias; alias="$(resolve_alias)"
  local line; line="$(remote "$alias" "squeue -j $jobid -h -o '%T|%r'" || true)"
  if [[ -z "$line" ]]; then
    echo "state:    not-in-queue (completed or purged — use: classify <run> $jobid)"
    return 0
  fi
  local state reason
  state="$(printf '%s' "$line" | head -1 | cut -d'|' -f1)"
  reason="$(printf '%s' "$line" | head -1 | cut -d'|' -f2)"
  echo "state:    $state"
  echo "reason:   $reason"
  echo "category: $(classify_reason "$reason")"
  echo "tasks:    $(printf '%s\n' "$line" | grep -c . )"
}

cmd_fetch() {
  local run="${1:?fetch: <run> required}"
  local alias repo; alias="$(resolve_alias)"; repo="$(resolve_repo)"
  mkdir -p "results/${run}"
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then
    echo "DRYRUN rsync -avz ${alias}:${repo}/results/${run}/ results/${run}/" >&2
    return 0
  fi
  rsync -avz "${alias}:${repo}/results/${run}/" "results/${run}/"
  echo "fetched -> results/${run}/"
}

cmd_classify() {
  local run="${1:?classify: <run> required}" jobid="${2:?classify: <jobid> required}"
  local alias; alias="$(resolve_alias)"
  local spec="results/${run}/run_spec.json"
  [[ -f "$spec" ]] || die "classify: missing $spec (run parameter_scan.py plan first)"
  local sacct; sacct="$(remote "$alias" "sacct -j $jobid --format=$SACCT_FMT -P" | parse_sacct || true)"
  echo -e "cell_id\tstate\texit-code\tmaxRSS\telapsed\tclassification"
  CLASSIFY_RUN="$run" SACCT_ROWS="$sacct" python3 - "$spec" <<'PY'
import json, os, sys
spec = json.load(open(sys.argv[1]))
cells = [c["cell_id"] for c in spec.get("cells", [])]
run = os.environ["CLASSIFY_RUN"]

def classify_state(state, code):
    if state == "COMPLETED": return "success"
    if state.startswith("OUT_OF_ME") or state.startswith("OOM"): return "oom"
    if state == "TIMEOUT": return "walltime"
    if state == "FAILED": return "logic-failure" if code == "0:0" else "nonzero-exit"
    if state.startswith("CANCELLED"): return "cancelled"
    if state in ("RUNNING", "PENDING", "REQUEUED"): return "in-progress"
    return f"unknown:{state}"

rows = {}
for line in os.environ.get("SACCT_ROWS", "").splitlines():
    if not line.strip():
        continue
    task, state, code, maxrss, elapsed = (line.split("\t") + ["", "", "", "", ""])[:5]
    rows[int(task)] = (state, code, maxrss, elapsed)

for idx, cell in enumerate(cells, start=1):
    if idx in rows:
        state, code, maxrss, elapsed = rows[idx]
        cls = classify_state(state, code)
    else:
        man = f"results/{run}/cells/{cell}/manifest.json"
        state, code, maxrss, elapsed = ("NO-SACCT", "", "", "")
        cls = "manifest-present" if os.path.isfile(man) else "no-record"
    print(f"{cell}\t{state}\t{code}\t{maxrss}\t{elapsed}\t{cls}")
PY
}

cmd_pending_cells() {
  local run="" success_field="" success_value="true"
  run="${1:?pending-cells: <run> required}"; shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --success-field) success_field="$2"; shift 2 ;;
      --success-value) success_value="$2"; shift 2 ;;
      *) die "pending-cells: unknown flag $1" ;;
    esac
  done
  local spec="results/${run}/run_spec.json"
  [[ -f "$spec" ]] || die "pending-cells: missing $spec"
  SUCCESS_FIELD="$success_field" SUCCESS_VALUE="$success_value" CLASSIFY_RUN="$run" \
    python3 - "$spec" <<'PY'
import json, os, sys
spec = json.load(open(sys.argv[1]))
run = os.environ["CLASSIFY_RUN"]
field = os.environ["SUCCESS_FIELD"]
want = os.environ["SUCCESS_VALUE"]

def dig(obj, path):
    for k in path.split("."):
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return None
    return obj

pending = []
for c in spec.get("cells", []):
    cid = c["cell_id"]
    man = f"results/{run}/cells/{cid}/manifest.json"
    ok = False
    if os.path.isfile(man):
        try:
            m = json.load(open(man))
            ok = True if not field else (str(dig(m, field)).lower() == want.lower())
        except (ValueError, OSError):
            ok = False
    if not ok:
        pending.append(cid)

for cid in pending:
    print(cid)
print(f"# {len(pending)}/{len(spec.get('cells', []))} cells still need a success-tagged manifest", file=sys.stderr)
PY
}

# Block until a job leaves the queue (polls squeue). Replaces agent-driven
# poll loops: monitoring is mechanism, not LLM turns. Scoped for short jobs —
# returns 2 on timeout so the caller can hand back rather than block forever.
# Knobs: --interval <s> (0 skips sleep, for tests), --attempts <n>.
cmd_wait() {
  local jobid="${1:?wait: <jobid> required}"; shift || true
  local interval="${HARNESS_WAIT_INTERVAL:-10}" attempts="${HARNESS_WAIT_ATTEMPTS:-180}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval) interval="$2"; shift 2 ;;
      --attempts) attempts="$2"; shift 2 ;;
      *) die "wait: unknown flag $1" ;;
    esac
  done
  local alias; alias="$(resolve_alias)"
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then
    echo "DRYRUN poll squeue -j $jobid every ${interval}s up to ${attempts} attempts" >&2
    return 0
  fi
  local i state
  for (( i=1; i<=attempts; i++ )); do
    state="$(remote "$alias" "squeue -j $jobid -h -o '%T'" 2>/dev/null | head -1)"
    if [[ -z "$state" ]]; then
      echo "state:    DONE (left queue) after $((i-1)) poll(s)"
      return 0
    fi
    echo "state:    $state (poll $i/$attempts)"
    [[ "$interval" == 0 ]] || sleep "$interval"
  done
  echo "state:    TIMEOUT (still ${state:-?} after $attempts polls); job continues — check later"
  return 2
}

# PASS/FAIL from a fetched smoke manifest. Split out so it is testable without
# a cluster (just a local results/<run>/manifest.json).
cmd_smoke_verdict() {
  local run="${1:?smoke-verdict: <run> required}"
  local man="results/${run}/manifest.json"
  if [[ ! -f "$man" ]]; then
    echo "VERDICT:  FAIL (no manifest at $man)"; return 1
  fi
  if grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' "$man"; then
    echo "VERDICT:  PASS ($man)"; return 0
  fi
  echo "VERDICT:  FAIL (status != ok in $man)"; return 1
}

# Canned end-to-end check: ship a trivial job, submit, wait, fetch, verdict.
# One call replaces the agent choreographing inspect/ship/submit/poll/fetch.
cmd_smoke_test() {
  local partition="" walltime="00:05:00" run="smoke" script="scripts/smoke_test.sbatch"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --partition) partition="$2"; shift 2 ;;
      --time) walltime="$2"; shift 2 ;;
      --run) run="$2"; shift 2 ;;
      *) die "smoke-test: unknown flag $1" ;;
    esac
  done
  [[ -f "$script" ]] || die "smoke-test: missing $script"
  local alias repo; alias="$(resolve_alias)"; repo="$(resolve_repo)"
  if [[ "${HARNESS_SLURM_DRYRUN:-0}" == "1" ]]; then
    echo "DRYRUN smoke-test plan:"
    echo "  1. ship $script -> $alias:$repo/scripts/"
    echo "  2. submit --script $script --partition ${partition:-<default>} --time $walltime"
    echo "  3. wait <jobid>"
    echo "  4. fetch $run"
    echo "  5. smoke-verdict $run"
    return 0
  fi
  echo "[1/5] ship $script"
  remote "$alias" "mkdir -p $repo/scripts $repo/results/$run"
  rsync -az "$script" "${alias}:${repo}/scripts/"
  echo "[2/5] submit"
  local out jobid
  out="$(cmd_submit --script "$script" ${partition:+--partition "$partition"} --time "$walltime")"
  printf '%s\n' "$out"
  jobid="$(printf '%s' "$out" | awk '/^job_id:/{print $2}')"
  [[ -n "$jobid" ]] || die "smoke-test: could not parse a job id"
  echo "[3/5] wait on $jobid"
  cmd_wait "$jobid" || true
  echo "[4/5] fetch $run"
  cmd_fetch "$run"
  echo "[5/5] verdict"
  cmd_smoke_verdict "$run"
}

# --- dispatch ----------------------------------------------------------------

# Global overrides accepted before the subcommand.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --alias) export HARNESS_SSH_ALIAS="$2"; shift 2 ;;
    --repo) export HARNESS_REPO_REMOTE="$2"; shift 2 ;;
    --profile) export HARNESS_PROFILE_FILE="$2"; shift 2 ;;
    --dry-run) export HARNESS_SLURM_DRYRUN=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) break ;;
  esac
done

sub="${1:-}"; shift || true
case "$sub" in
  precheck)         cmd_precheck "$@" ;;
  probe-partitions) cmd_probe_partitions "$@" ;;
  submit)           cmd_submit "$@" ;;
  status)           cmd_status "$@" ;;
  wait)             cmd_wait "$@" ;;
  smoke-test)       cmd_smoke_test "$@" ;;
  smoke-verdict)    cmd_smoke_verdict "$@" ;;
  fetch)            cmd_fetch "$@" ;;
  classify)         cmd_classify "$@" ;;
  pending-cells)    cmd_pending_cells "$@" ;;
  parse-sinfo)      parse_sinfo ;;
  parse-sacct)      parse_sacct ;;
  classify-reason)  classify_reason "${1:-}" ;;
  classify-state)   classify_state "${1:-}" "${2:-}" ;;
  ""|-h|--help)     sed -n '2,40p' "$0" ;;
  *) die "unknown subcommand '$sub' (try --help)" ;;
esac
