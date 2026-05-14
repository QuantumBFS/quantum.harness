#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
if printf '%s' "$input" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
flow="$repo_root/tools/cli/flow"

flow_dir="${1:-${HARNESS_FLOW_DIR:-}}"
gate="${2:-${HARNESS_FLOW_GATE:-close}}"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if [[ -z "$flow_dir" ]]; then
  exit 0
fi

if "$flow" require "$flow_dir" "$gate" >/dev/null 2>&1; then
  exit 0
fi

next_gate="$("$flow" next "$flow_dir" 2>/dev/null | sed -n '1p' || true)"

if [[ -n "$next_gate" ]]; then
  reason="Harness flow '$flow_dir' is not closed; next runnable gate is '$next_gate'. Continue by recording the next attempt/artifacts, then run: tools/cli/flow require $flow_dir $gate"
  printf '{"decision":"block","reason":"%s"}\n' "$(json_escape "$reason")"
else
  message="Harness flow '$flow_dir' is not closed and has no runnable gate. Stop and surface the blocker or ask the user to choose repair, narrow, deviation, or stop."
  printf '{"systemMessage":"%s"}\n' "$(json_escape "$message")"
fi
