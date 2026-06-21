#!/bin/bash
#SBATCH --job-name=harness-netcheck
#SBATCH --output=results/netcheck/netcheck-%j.out
# Decide whether compute nodes have outbound internet — gates the software-env
# strategy (in-job installs vs fully pre-staged / containerized).
set -uo pipefail
mkdir -p results/netcheck
host=$(hostname)
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://github.com 2>/dev/null || echo "000")
julia_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://pkg.julialang.org 2>/dev/null || echo "000")
reachable="no"; [ "$code" = "200" ] && reachable="yes"
echo "host=$host"
echo "github_http=$code"
echo "julia_pkg_http=$julia_code"
echo "internet_from_compute=$reachable"
printf '{"host":"%s","github_http":"%s","julia_pkg_http":"%s","internet_from_compute":"%s"}\n' \
  "$host" "$code" "$julia_code" "$reachable" > results/netcheck/manifest.json
