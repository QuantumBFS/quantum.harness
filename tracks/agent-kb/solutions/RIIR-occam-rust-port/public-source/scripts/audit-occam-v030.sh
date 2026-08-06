#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

echo "[1/9] source hygiene"
git diff --check
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings

echo "[2/9] debug and release test suites"
cargo test --workspace
cargo test --workspace --release

echo "[3/9] fuzz target compilation"
if command -v rustup >/dev/null 2>&1 &&
    rustup toolchain list | grep -q '^nightly'; then
    cargo +nightly fuzz check --fuzz-dir fuzz
else
    echo "nightly rustup toolchain unavailable; compiling every fuzz binary with stable Cargo"
    cargo check --manifest-path fuzz/Cargo.toml --bins
fi

echo "[4/9] pinned external inputs"
./scripts/fetch-occam-data.sh
./scripts/fetch-abc.sh

echo "[5/9] complete solution regeneration"
./scripts/solve-occam71.sh --check

echo "[6/9] independent public snapshot"
./scripts/update-occam71-submission-snapshot --check
challenge-71-occam/solutions/rewrite-it-in-rust/search/run-all.sh --check

echo "[7/9] independent Julia and evidence verification"
julia --startup-file=no scripts/verify-occam71.jl
./scripts/verify-oracles.sh
./scripts/verify-synthesis-evidence.sh

echo "[8/9] immutable v0.3 and measured v2 JSON assertions"
node --input-type=module <<'NODE'
import crypto from "node:crypto";
import fs from "node:fs";

const readJson = (path) => JSON.parse(fs.readFileSync(path, "utf8"));
const hash = (path) =>
  crypto.createHash("sha256").update(fs.readFileSync(path)).digest("hex");
const solution = "challenge-71-occam/solutions/rewrite-it-in-rust";
const manifest = readJson(`${solution}/manifest.json`);
if (
  manifest.schema_version !== 2 ||
  manifest.learner !== "mdl-enumerator" ||
  manifest.baseline_tag !== "v0.2.0"
) throw new Error("solution manifest is not the v0.3.0 research schema");
if (manifest.instances.length !== 4) throw new Error("solution has wrong instance count");
const counts = Object.fromEntries(
  manifest.instances.map((instance) => [instance.instance, instance.gate_count]),
);
if (JSON.stringify(counts) !== JSON.stringify({
  "mystery-A": 37,
  "mystery-B": 50,
  "mystery-C": 167,
  "mystery-D": 186,
})) throw new Error(`unexpected optimized gate counts: ${JSON.stringify(counts)}`);
for (const instance of manifest.instances) {
  if (instance.prediction_sha256 !== instance.expected_commitment_sha256) {
    throw new Error(`${instance.instance} commitment changed`);
  }
}
if (
  hash(`${solution}/${manifest.optimization_report_path}`) !==
    manifest.optimization_report_sha256 ||
  hash(`${solution}/${manifest.research_manifest_path}`) !==
    manifest.research_manifest_sha256
) throw new Error("transitive solution hashes do not match");

const rooted = readJson(`${solution}/research-manifest.json`);
if (rooted.trial_rows !== 20_480) throw new Error("wrong rooted trial count");
const expressions = Object.fromEntries(
  Object.entries(rooted.official_mdl_reports).map(([key, value]) => [
    key,
    value.expression,
  ]),
);
if (JSON.stringify(expressions) !== JSON.stringify({
  "mystery-A": "(x + y)",
  "mystery-B": "abs(x - y)",
  "mystery-C": "(x * y)",
  "mystery-D": "(square(x) + square(y))",
})) throw new Error("official MDL recovery changed");

const aggregate = readJson("experiments/occam-generalization/aggregate.json");
if (aggregate.trial_rows !== 20_480 || aggregate.group_rows !== 1_024) {
  throw new Error("research matrix is incomplete");
}
if (aggregate.groups.some((group) => group.missing_trials !== 0)) {
  throw new Error("research matrix has missing trials");
}
if (aggregate.correlations.paired_trials !== 8_380) {
  throw new Error("paired correlation population changed");
}
for (const figure of [
  "gates-vs-accuracy.svg",
  "fraction-vs-recovery.svg",
  "description-vs-gates.svg",
]) {
  const path = `experiments/occam-generalization/figures/${figure}`;
  const expected = readJson("experiments/occam-generalization/manifest.json")
    .files[`figures/${figure}`];
  if (hash(path) !== expected) throw new Error(`${figure} hash mismatch`);
}
const lock = readJson("tools/abc/LOCK.json");
if (lock.commit !== "e76768b9d34f9dc67cb6608efecd55db271ff849") {
  throw new Error("ABC pin changed");
}

const v2root = "experiments/occam-generalization-v2";
const v2manifest = readJson(`${v2root}/manifest.json`);
if (v2manifest.schema_version !== 2 || v2manifest.trial_rows !== 20_480) {
  throw new Error("measured v2 research manifest is incomplete");
}
for (const [relative, expected] of Object.entries(v2manifest.files)) {
  if (hash(`${v2root}/${relative}`) !== expected) {
    throw new Error(`v2 research hash mismatch: ${relative}`);
  }
}
const measured = fs.readFileSync(`${v2root}/raw-measured.jsonl`, "utf8")
  .trimEnd().split("\n").map(JSON.parse);
const semantic = fs.readFileSync(`${v2root}/semantic.jsonl`, "utf8")
  .trimEnd().split("\n").map(JSON.parse);
if (measured.length !== 20_480 || semantic.length !== measured.length) {
  throw new Error("measured and semantic v2 row counts differ");
}
if (measured.some((row) =>
  row.runtime_micros <= 0 ||
  row.peak_rss_bytes <= 0 ||
  !row.host_identifier ||
  row.process_id <= 0 ||
  row.started_unix_micros <= 0
)) throw new Error("v2 measured rows contain placeholder process measurements");
const measuredKeys = new Set(measured.map((row) => JSON.stringify(row.key)));
const semanticKeys = new Set(semantic.map((row) => JSON.stringify(row.key)));
if (measuredKeys.size !== 20_480 || semanticKeys.size !== 20_480) {
  throw new Error("v2 trial keys are missing or duplicated");
}
for (const key of measuredKeys) {
  if (!semanticKeys.has(key)) throw new Error(`v2 semantic row missing: ${key}`);
}
const v2aggregate = readJson(`${v2root}/aggregate.json`);
if (
  v2aggregate.schema_version !== 2 ||
  v2aggregate.trial_rows !== 20_480 ||
  v2aggregate.group_rows !== 1_024 ||
  v2aggregate.groups.some((group) => group.missing_trials !== 0)
) throw new Error("v2 aggregate is incomplete");
for (const group of v2aggregate.groups) {
  if (
    group.statuses.success > 0 &&
    (!(group.median_runtime_micros > 0) || !(group.median_peak_rss_bytes > 0))
  ) throw new Error("v2 successful aggregate has a zero measurement");
}
NODE

echo "[9/9] secret and scope scan"
secret_pattern='(gho[_]|github[_]pat[_]|BEGIN (RSA|OPENSSH|EC) PRIVATE K[E]Y|AWS[_]SECRET_ACCESS_KEY)'
if rg -n --hidden \
    "$secret_pattern" \
    . \
    -g '!target/**' \
    -g '!challenge-71-occam/solutions/rewrite-it-in-rust/search/target/**' \
    -g '!docs/superpowers/plans/**' \
    -g '!.git/**'; then
    echo "possible secret material found" >&2
    exit 1
fi

echo "Immutable Occam v0.3.0 and measured v2 local audits passed."
