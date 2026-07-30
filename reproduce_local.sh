#!/bin/bash
# Root-level convenience wrapper; the canonical script lives in the team folder.
exec "$(dirname "$0")/tracks/polyopt/solutions/its-a-trap/reproduce_local.sh" "$@"
