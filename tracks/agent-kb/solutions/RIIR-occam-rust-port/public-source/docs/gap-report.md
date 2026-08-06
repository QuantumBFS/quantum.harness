# Rust Port Gap Report

## Closed Compatibility Gaps

| Area | Finding | Resolution |
|---|---|---|
| Bit order | Dataset characters are semantic bit positions in LSB-first order, not integers to be endian-converted. | Parsers preserve character order; exhaustive arithmetic tests cover interpretation. |
| Wire identifiers | Official netlists expose arbitrary positive `wN` identifiers while evaluators benefit from dense storage. | Parser maps external identifiers to dense zero-based indices. |
| Inversion | `~` is legal on operands and outputs and must not count as a gate. | Inversion is a flag on `Operand`, separate from `Gate`. |
| Definition order | Wire operands must be defined before use. | Parser validates definition-before-use and duplicate definitions. |
| Metrics | Exact-match and bit accuracy measure different failure modes. | Rust records exact matches and correct bits separately before calculating ratios. |
| Reproducibility | The official release archive should not be copied without provenance. | Fetch script pins both release URL and SHA-256. |
| Packed evaluation | Complement operations set unused high bits in a final partial machine word. | Every accuracy operation applies an explicit valid-sample tail mask. |
| Backend trust | A fast backend could reproduce rounded accuracy while differing in counts. | Cross-check compares the complete `VerificationMetrics` and randomized tests cover all 64-bit boundaries. |
| Benchmark separation | Startup, parsing, packing, and gate evaluation answer different questions. | Rust JSON reports parse, one-time packing, and repeated evaluation independently; process results are labeled startup-inclusive. |
| Packed allocation | Nested per-column/per-wire vectors add allocation and pointer-chasing overhead. | Packed datasets and wire values use flat contiguous arenas; retained A/B evidence shows improvements outside combined MAD. |
| Repeated interpretation | Resolving enum operands inside every block repeats invariant work. | `CompiledCircuit` pre-resolves columns and inversion masks; default packed execution is 2.49–3.29× faster than the retained interpreted backend. |
| Unbounded inputs | Public parsers and evaluators could otherwise accept impractical sizes or overflow derived counts. | Checked arithmetic and explicit source, shape, gate, sample, packed-word, and generated-byte limits return distinct errors instead of panicking. |
| Differential confidence | Hand-picked fixtures cannot cover all operator/inversion/boundary combinations. | 1,000 seeded property cases plus four nightly fuzz targets cover parser and evaluator equivalence. |
| Small-circuit learning | The migration initially only verified known circuits. | An embedded SAT backend now learns complete truth tables, searches increasing gate bounds, extracts official netlists, and independently re-verifies SAT models. |

## Open Gaps

| Area | Current state | Next evidence |
|---|---|---|
| CSV CPU time | Direct packed ingestion retains strict two-pass validation and uses 2.4–3.7× less peak RSS, but its pure parse/pack CPU time is 4–14% slower than scalar parse plus packing in the recorded cases. | Optimize the shared scanner or add a safely validated single-pass staging design; retain the direct path for its memory and end-to-end behavior. |
| Error parity | Rust errors are more structured and stricter than the small Julia script. | Document intentional strictness and test every accepted official fixture. |
| Circuit-learning scale | Exact half-adder synthesis finishes immediately, but a 30-second exhaustive two-bit-adder run proves bounds 0–5 UNSAT and then times out while solving gate bound 6. | Add commutativity/symmetry breaking, reuse clauses incrementally across bounds, and evaluate proof logging/checking before making stronger minimality claims. |
| UNSAT evidence | Varisat returns UNSAT for tested bounds, but the certificate does not contain a DRAT or independently checkable proof trace. | Add optional proof output and a separate checker if formal minimality evidence becomes a project requirement. |
| Upstream packaging | The crate is currently a workspace member, not a published reusable library. | Decide whether the stable parser/evaluator API should be published or contributed with the #115 solution. |

## Initial Rust Ecosystem Assessment

This workload does not require a scientific tensor library, automatic
differentiation, an eigensolver, or a GPU runtime. Rust's standard data
structures are sufficient for the trusted scalar baseline. The language's
typed enums make unsupported gate states unrepresentable after parsing, while
structured errors provide more context than the reference script.

Measurements answer the initial performance question: compiled `u64` packing
improves evaluator median time by 131–191× and remains 2.3–5.7× faster in the
production one-shot comparison after parsing and compilation are charged. This
required no unsafe code, Rayon, or explicit SIMD.

The performance bottleneck consequently moves to strict dataset ingestion,
while the scientific-extension bottleneck is SAT scaling at UNSAT lower
bounds. Full methodology and limitations are in
`benchmarks/results/2026-07-28-apple-m4.md`, and bounded synthesis evidence is
in `docs/synthesis/README.md`.
