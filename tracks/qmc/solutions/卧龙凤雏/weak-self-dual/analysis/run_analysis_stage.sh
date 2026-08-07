#!/usr/bin/env bash
set -u

run_dir="$1"
start_time="$2"
renderer="$3"
python_bin="$4"
finalizer="$5"
shift 5

analysis_status=0
"$@" || analysis_status=$?

if [[ -f "$run_dir/report.json" ]]; then
  end_time="$(perl -MTime::HiRes=clock_gettime,CLOCK_MONOTONIC -e 'print clock_gettime(CLOCK_MONOTONIC)')"
  elapsed="$(perl -e 'print $ARGV[1] - $ARGV[0]' "$start_time" "$end_time")"
  finalizer_status=0
  "$python_bin" "$finalizer" "$run_dir" "$elapsed" --renderer "$renderer" || finalizer_status=$?
  if [[ "$finalizer_status" -ne 0 && "$analysis_status" -eq 0 ]]; then
    analysis_status="$finalizer_status"
  fi
fi

exit "$analysis_status"
