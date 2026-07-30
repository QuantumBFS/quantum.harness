#!/usr/bin/env bash
# Optional DaemonMode.jl runner for reducing repeated Julia time-to-first-execution.
# DaemonMode is installed in a dedicated tool environment, never in the compute
# project passed through --project. This unauthenticated localhost service is
# intended only for trusted, single-user workstations.

set -euo pipefail

JULIA_BIN="${JULIA_REAL_BIN:-${JULIA_BIN:-$(command -v julia 2>/dev/null || true)}}"
PORT="${JULIA_DAEMON_PORT:-3000}"
CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/quantum-harness/julia-daemon"
TOOL_ENV="${JULIA_DAEMON_TOOL_ENV:-$CACHE_ROOT/tool-environment}"
STARTING_PID=""
LOCK_HELD=0

cleanup_on_exit() {
  rc=$?
  if [ "$rc" -ne 0 ] && [ -n "$STARTING_PID" ] && kill -0 "$STARTING_PID" 2>/dev/null; then
    kill "$STARTING_PID" 2>/dev/null || true
  fi
  if [ "$LOCK_HELD" -eq 1 ]; then
    release_lock
  fi
}
trap cleanup_on_exit EXIT

usage() {
  cat <<'EOF'
Usage:
  scripts/julia-daemon.sh install
  scripts/julia-daemon.sh install-shim [PATH]
  eval "$(scripts/julia-daemon.sh alias)"
  scripts/julia-daemon.sh julia JULIA_ARGS...
  scripts/julia-daemon.sh run [--port N] --project DIR (-e CODE | SCRIPT [ARGS...])
  scripts/julia-daemon.sh start [--port N] --project DIR
  scripts/julia-daemon.sh status [--port N]
  scripts/julia-daemon.sh stop [--port N]

DaemonMode is installed in a dedicated cache environment. The target compute
project is not modified. This opt-in runner opens an unauthenticated localhost
service and is only for trusted, single-user workstations; do not use it on
shared login or compute nodes. The optional shim lets normal `julia --project`
commands use the daemon when compatible and otherwise executes real Julia.
Set JULIA_REAL_BIN to the real Julia executable (not another wrapper).

WARNING: The daemon retains compiled code, loaded modules, task-local/global
state, and allocations between calls. Resident memory can keep growing and may
cause an out-of-memory (OOM) kill during large or varied workloads. Results can
also depend on state left by an earlier call, and source or environment changes
may not be visible in the already-running process. Run
`scripts/julia-daemon.sh stop [--port N]` to release memory and reset state;
restart after dependency, environment, or substantial source changes.
EOF
}

fail() {
  echo "julia-daemon: $*" >&2
  exit 1
}

require_julia() {
  [ -n "$JULIA_BIN" ] && [ -x "$JULIA_BIN" ] || \
    fail "Julia not found; run 'make install julia' first"
}

resolve_real_julia() {
  require_julia
  JULIA_BIN=$("$JULIA_BIN" --startup-file=no -e 'print(realpath(Sys.BINDIR * "/" * Base.julia_exename()))')
  [ -x "$JULIA_BIN" ] || fail "could not resolve the real Julia executable"
}

install_daemonmode() {
  resolve_real_julia
  mkdir -p "$TOOL_ENV"
  "$JULIA_BIN" --startup-file=no --project="$TOOL_ENV" -e \
    'using Pkg; Pkg.add(name="DaemonMode", version="0.1"); Pkg.precompile()'
  "$JULIA_BIN" --startup-file=no --project="$TOOL_ENV" -e \
    'using DaemonMode; println("DaemonMode ", pkgversion(DaemonMode), " ready in dedicated tool environment")'
}

runner_path() {
  runner=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")
}

install_shim() {
  runner_path
  shim_path="${1:-$HOME/.local/bin/julia}"
  case "$shim_path" in /*) ;; *) shim_path="$PWD/$shim_path";; esac
  if [ -e "$shim_path" ] && [ "$shim_path" -ef "$runner" ]; then
    fail "refusing to replace the daemon runner itself"
  fi
  resolve_real_julia
  if [ -e "$shim_path" ]; then
    first_line=$(IFS= read -r line <"$shim_path" && printf '%s' "$line")
    second_line=$("$JULIA_BIN" --startup-file=no -e 'println(readlines(ARGS[1])[2])' -- "$shim_path" 2>/dev/null || true)
    [ "$first_line" = "#!/usr/bin/env bash" ] && \
      [ "$second_line" = "# quantum-harness-julia-daemon-shim" ] || \
      fail "refusing to replace existing file: $shim_path"
  fi
  mkdir -p "$(dirname "$shim_path")"
  quoted_julia=$(printf '%q' "$JULIA_BIN")
  quoted_runner=$(printf '%q' "$runner")
  cat >"$shim_path" <<EOF
#!/usr/bin/env bash
# quantum-harness-julia-daemon-shim
export JULIA_REAL_BIN=$quoted_julia
exec $quoted_runner julia "\$@"
EOF
  chmod 0755 "$shim_path"
  echo "Julia shim installed at $shim_path"
  echo "Ensure $(dirname "$shim_path") appears before $(dirname "$JULIA_BIN") in PATH."
}

print_alias() {
  resolve_real_julia
  runner_path
  command="env JULIA_REAL_BIN=$(printf '%q' "$JULIA_BIN") $(printf '%q' "$runner") julia"
  printf 'alias julia=%q\n' "$command"
}

parse_port() {
  if [ "${1:-}" = "--port" ]; then
    [ $# -ge 2 ] || fail "--port requires a value"
    PORT="$2"
    shift 2
  fi
  case "$PORT" in
    ''|*[!0-9]*) fail "port must be an integer";;
  esac
  [ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ] || fail "port must be between 1 and 65535"
  REMAINING=("$@")
}

set_state_paths() {
  STATE_DIR="$CACHE_ROOT/$PORT"
  PID_FILE="$STATE_DIR/server.pid"
  PROJECT_FILE="$STATE_DIR/project"
  LOG_FILE="$STATE_DIR/server.log"
  TOKEN_FILE="$STATE_DIR/server.token"
  IDENTITY_FILE="$STATE_DIR/server.identity"
  LOCK_DIR="$STATE_DIR/lock"
}

read_positive_pid() {
  [ -s "$PID_FILE" ] || return 1
  pid=$(cat "$PID_FILE")
  case "$pid" in ''|*[!0-9]*|0) return 1;; esac
  return 0
}

pid_matches_state() {
  read_positive_pid || return 1
  [ -s "$TOKEN_FILE" ] && [ -s "$IDENTITY_FILE" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  token=$(cat "$TOKEN_FILE")
  expected=$(cat "$IDENTITY_FILE")
  case "$token" in ''|*[!A-Za-z0-9_.-]*) return 1;; esac
  if [ -r "/proc/$pid/cmdline" ]; then
    actual=$(tr '\0' ' ' <"/proc/$pid/cmdline")
  else
    actual=$(ps -p "$pid" -o command= 2>/dev/null || true)
  fi
  if [[ "$actual" == *"$expected"* && "$actual" == *"$token"* ]]; then
    return 0
  fi
  return 1
}

acquire_lock() {
  mkdir -p "$STATE_DIR"
  count=0
  until mkdir "$LOCK_DIR" 2>/dev/null; do
    count=$((count + 1))
    [ "$count" -lt 300 ] || fail "timed out waiting for state lock on port $PORT"
    sleep 0.1
  done
  LOCK_HELD=1
}

release_lock() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
  LOCK_HELD=0
}

clear_state() {
  rm -f "$PID_FILE" "$PROJECT_FILE" "$TOKEN_FILE" "$IDENTITY_FILE"
}

stop_server_locked() {
  if pid_matches_state; then
    kill "$pid" 2>/dev/null || true
    count=0
    while kill -0 "$pid" 2>/dev/null && [ "$count" -lt 50 ]; do
      sleep 0.1
      count=$((count + 1))
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
  elif [ -s "$PID_FILE" ]; then
    echo "julia-daemon: refusing to signal an unverified stale PID" >&2
  fi
  clear_state
}

stop_server() {
  set_state_paths
  acquire_lock
  trap release_lock RETURN
  stop_server_locked
  release_lock
  trap - RETURN
}

normalize_project() {
  project="$1"
  [ "$project" = "@." ] && project="$PWD"
  case "$project" in
    /*) ;;
    *) project="$PWD/$project";;
  esac
  project=$("$JULIA_BIN" --startup-file=no -e 'print(realpath(ARGS[1]))' -- "$project")
  [ -f "$project/Project.toml" ] || fail "no Project.toml in $project"
  PROJECT="$project"
}

parse_project() {
  [ "${1:-}" = "--project" ] || fail "--project DIR is required"
  [ $# -ge 2 ] || fail "--project requires a directory"
  normalize_project "$2"
  REMAINING=("${@:3}")
}

check_daemonmode() {
  "$JULIA_BIN" --startup-file=no --project="$TOOL_ENV" -e 'using DaemonMode' >/dev/null 2>&1 || \
    fail "DaemonMode is not installed; run '$0 install'"
}

start_server() {
  require_julia
  check_daemonmode
  set_state_paths
  acquire_lock
  trap release_lock RETURN

  if pid_matches_state; then
    active_project=$(cat "$PROJECT_FILE" 2>/dev/null || true)
    if [ "$active_project" != "$PROJECT" ]; then
      release_lock
      trap - RETURN
      fail "port $PORT already serves $active_project; choose another --port or stop it"
    fi
    release_lock
    trap - RETURN
    return 0
  fi

  clear_state
  : >"$LOG_FILE"
  token="$(date +%s).$$.$RANDOM"
  identity="quantum-harness-daemon-$PORT"
  load_path="$PROJECT:$TOOL_ENV:@stdlib"
  JULIA_DAEMON_PORT="$PORT" JULIA_DAEMON_TOKEN="$token" JULIA_LOAD_PATH="$load_path" \
    nohup "$JULIA_BIN" --startup-file=no --project="$PROJECT" \
    -e 'using DaemonMode; token=ENV["JULIA_DAEMON_TOKEN"]; serve(parse(Int, ENV["JULIA_DAEMON_PORT"]), false; async=false)' \
    "$identity" "$token" >>"$LOG_FILE" 2>&1 &
  server_pid=$!
  STARTING_PID="$server_pid"
  printf '%s\n' "$server_pid" >"$PID_FILE.tmp"
  printf '%s\n' "$PROJECT" >"$PROJECT_FILE.tmp"
  printf '%s\n' "$token" >"$TOKEN_FILE.tmp"
  printf '%s\n' "$identity" >"$IDENTITY_FILE.tmp"
  mv "$PID_FILE.tmp" "$PID_FILE"
  mv "$PROJECT_FILE.tmp" "$PROJECT_FILE"
  mv "$TOKEN_FILE.tmp" "$TOKEN_FILE"
  mv "$IDENTITY_FILE.tmp" "$IDENTITY_FILE"

  count=0
  while [ "$count" -lt 120 ]; do
    kill -0 "$server_pid" 2>/dev/null || {
      echo "julia-daemon: server failed; log: $LOG_FILE" >&2
      clear_state
      STARTING_PID=""
      release_lock
      trap - RETURN
      return 1
    }
    # A client probe validates both the listening socket and the protocol. Julia
    # startup dominates this check, so probe twice per second rather than spin.
    probe=$(JULIA_DAEMON_PORT="$PORT" "$JULIA_BIN" --startup-file=no --project="$TOOL_ENV" \
      -e 'using DaemonMode; runexpr("println(\"daemon-ready\")"; port=parse(Int, ENV["JULIA_DAEMON_PORT"]))' \
      2>/dev/null || true)
    case "$probe" in
      *daemon-ready*) STARTING_PID=""; release_lock; trap - RETURN; return 0;;
    esac
    sleep 0.5
    count=$((count + 1))
  done

  echo "julia-daemon: server timed out; log: $LOG_FILE" >&2
  stop_server_locked
  STARTING_PID=""
  release_lock
  trap - RETURN
  return 1
}

run_client() {
  [ ${#REMAINING[@]} -gt 0 ] || fail "-e CODE or SCRIPT is required"
  start_server

  client='using DaemonMode; DaemonMode.runargs(parse(Int, ENV["JULIA_DAEMON_PORT"]))'
  if [ "${REMAINING[0]}" = "-e" ] || [ "${REMAINING[0]}" = "--eval" ]; then
    [ ${#REMAINING[@]} -ge 2 ] || fail "-e requires Julia code"
    code="${REMAINING[1]}"
    args=("${REMAINING[@]:2}")
    tmp=$(mktemp "$STATE_DIR/eval.XXXXXX.jl")
    trap 'rm -f "$tmp"' EXIT
    printf '%s\n' "$code" >"$tmp"
    target="$tmp"
  else
    target="${REMAINING[0]}"
    args=("${REMAINING[@]:1}")
    [ -f "$target" ] || fail "script not found: $target"
  fi

  # DaemonMode 0.1.x cannot round-trip whitespace inside a single script
  # argument. Reject rather than silently changing ARGS semantics.
  for arg in "${args[@]}"; do
    case "$arg" in
      *[[:space:]]*) fail "arguments containing whitespace are not supported by DaemonMode";;
    esac
  done

  JULIA_DAEMON_PORT="$PORT" "$JULIA_BIN" --startup-file=no --project="$TOOL_ENV" \
    -e "$client" -- "$target" "${args[@]}"
}

fallback_julia() {
  exec "$JULIA_BIN" "$@"
}

derive_port() {
  key="$PROJECT|$PWD"
  checksum=$(printf '%s' "$key" | cksum)
  checksum=${checksum%% *}
  PORT=$((20000 + checksum % 30000))
}

auto_julia() {
  require_julia
  original=("$@")
  [ $# -ge 2 ] || fallback_julia "${original[@]}"

  case "$1" in
    --project=*) project_arg="${1#--project=}"; shift;;
    *) fallback_julia "${original[@]}";;
  esac
  case "$project_arg" in ''|@*) fallback_julia "${original[@]}";; esac

  case "$1" in
    -e|--eval)
      [ $# -ge 2 ] || fallback_julia "${original[@]}"
      for arg in "${@:3}"; do
        case "$arg" in *[[:space:]]*) fallback_julia "${original[@]}";; esac
      done
      ;;
    -*) fallback_julia "${original[@]}";;
    *)
      case "$1" in *.jl) ;; *) fallback_julia "${original[@]}";; esac
      [ -f "$1" ] || fallback_julia "${original[@]}"
      for arg in "${@:2}"; do
        case "$arg" in *[[:space:]]*) fallback_julia "${original[@]}";; esac
      done
      ;;
  esac

  normalize_project "$project_arg"
  derive_port
  REMAINING=("$@")
  run_client
}

cmd="${1:-help}"
[ $# -eq 0 ] || shift
case "$cmd" in
  install)
    [ $# -eq 0 ] || fail "install takes no arguments"
    install_daemonmode
    ;;
  install-shim)
    [ $# -le 1 ] || fail "install-shim accepts at most one path"
    install_daemonmode
    install_shim "${1:-}"
    ;;
  alias)
    [ $# -eq 0 ] || fail "alias takes no arguments"
    print_alias
    ;;
  julia)
    auto_julia "$@"
    ;;
  start)
    parse_port "$@"; parse_project "${REMAINING[@]}"
    [ ${#REMAINING[@]} -eq 0 ] || fail "unexpected arguments after project"
    start_server
    echo "Julia daemon running on port $PORT for $PROJECT"
    ;;
  run)
    parse_port "$@"; parse_project "${REMAINING[@]}"
    run_client
    ;;
  status)
    parse_port "$@"
    [ ${#REMAINING[@]} -eq 0 ] || fail "status only accepts --port"
    set_state_paths
    if pid_matches_state; then
      echo "running pid=$(cat "$PID_FILE") port=$PORT project=$(cat "$PROJECT_FILE")"
    else
      echo "stopped port=$PORT"
      exit 1
    fi
    ;;
  stop)
    parse_port "$@"
    [ ${#REMAINING[@]} -eq 0 ] || fail "stop only accepts --port"
    stop_server
    echo "Julia daemon stopped on port $PORT"
    ;;
  help|-h|--help) usage;;
  *) usage >&2; exit 2;;
esac
