# lifeIsShort — Challenge #71: Occam's Circuit

Four compact arithmetic circuits selected from sparse public examples, with
deterministic candidate generation and reproducible public-input predictions.

## Registration

| | |
|---|---|
| **Team name** | lifeIsShort |
| **Members** | Shigang Ou (@osgood001) |
| **Challenge** | Recover hidden arithmetic Boolean functions from sparse input-output examples by finding compact consistent circuits that generalize beyond the training data, rather than memorizing partial truth tables. |
| **Catalog issue** | [`Addresses #71`](https://github.com/QuantumBFS/quantum.harness/issues/71) — “Occam's Circuit — recover a hidden logic function from polynomially many examples,” released by Jin-Guo Liu, HKUST(Guangzhou). |
| **Track** | `tracks/qcs/` — specified by the challenge issue's Deliverables section. |

## Submission

Inputs contain two unsigned, LSB-first operands; outputs are also LSB-first.
Under the official free-inversion convention, the four candidates are:

| Instance | Selected arithmetic family | Operand → output width | Public-training exact fit | Candidate | Gates |
|---|---|---:|---:|---|---:|
| A | `x + y` | 8 + 8 → 9 bits | 2000/2000 | [`mystery-A.txt`](mystery-A.txt) | **37** |
| B | `|x − y|` | 7 + 7 → 7 bits | 1500/1500 | [`mystery-B.txt`](mystery-B.txt) | **50** |
| C | `x × y` | 6 + 6 → 12 bits | 1200/1200 | [`mystery-C.txt`](mystery-C.txt) | **168** |
| D | `x² + y²` | 5 + 5 → 11 bits | 400/400 | [`mystery-D.txt`](mystery-D.txt) | **225** |

`infer_functions.py` deterministically scores exactly four declared families
— addition, absolute difference, multiplication, and sum of squares — on the
released training rows, then ranks all 4! one-to-one assignments by the sum of
exact per-dataset training accuracies, with fixed dataset/family order as the
tie-break. This is **selection among four declared arithmetic families**, not
unrestricted function discovery.

`generate_circuits.py` turns the selected families into fan-in-two Boolean
netlists: a ripple-carry adder for A, a subtractor with borrow-controlled
magnitude correction for B, a shift-and-add multiplier for C, and two squaring
networks plus an adder for D. It performs deterministic constant folding and
gate reuse. The reported sizes are valid candidate sizes, **not proofs of
minimality**.

## Predictions, evidence, and scoring

`generate_test_outputs.py` verifies the official release asset, reads only the
four public `test_inputs.csv` members, evaluates the declared arithmetic, checks
that each candidate circuit agrees, and writes the four
`predictions/mystery-{A,B,C,D}/test_outputs.csv` files in public-input order.

The evidence has four distinct scopes:

- **Public-training exact fit:** each selected family and candidate matches
  every released training row, as reported in the table.
- **Exhaustive synthetic checks:** `test_generator.py` evaluates every input
  pair in each declared finite-width arithmetic domain. This proves the
  generated circuits implement those declared families; it does not measure
  generalization from sparse data.
- **SHA-256 commitment identity:** each complete prediction CSV matches its
  published SHA-256 commitment. This is a byte-level identity statement.
- **Hidden-test accuracy:** no withheld output file was opened or compared
  row-by-row, so hidden exact-match and bit accuracies remain unmeasured here.

> Official ranking is **exact-match accuracy on the hidden test set first**;
> **fewer gates break ties**. Bit accuracy is a verifier diagnostic, not a
> leaderboard ranking criterion.

Only one circuit size is reported per family, and hidden-test accuracy has not
been measured. The relationship between circuit size and generalization is
therefore **not yet established** by this submission.

## Reproduce

The coherent submission closure contains exactly 20 files, relative to this
directory:

| Role | Files | Count |
|---|---|---:|
| Pitch | `README.md` | 1 |
| Programs | `evaluator.py`, `infer_functions.py`, `generate_circuits.py`, `generate_test_outputs.py`, `run_controls.py` | 5 |
| Public controls | `controls/practice-add-n4.txt`, `controls/practice-mul-n4.txt` | 2 |
| Candidate circuits | `mystery-A.txt`, `mystery-B.txt`, `mystery-C.txt`, `mystery-D.txt` | 4 |
| Public-input predictions | `predictions/mystery-{A,B,C,D}/test_outputs.csv` | 4 |
| Tests | `tests/test_evaluator.py`, `tests/test_infer_functions.py`, `tests/test_generator.py`, `tests/test_generate_test_outputs.py` | 4 |
| **Total** |  | **20** |

Run from the repository root. All generated validation artifacts below stay in
a fresh temporary directory:

```sh
solution=tracks/qcs/solutions/lifeIsShort
scratch="$(mktemp -d)"
asset="$scratch/occam-circuit.zip"
export PYTHONDONTWRITEBYTECODE=1

curl -fL \
  https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip \
  -o "$asset"
test "$(wc -c < "$asset")" -eq 61068
printf '%s  %s\n' \
  c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b \
  "$asset" | sha256sum -c -

unzip -q "$asset" -d "$scratch/release"

python3 "$solution/infer_functions.py" \
  "$scratch/release/occam-circuit/datasets" \
  > "$scratch/inference.json"

python3 "$solution/generate_circuits.py" \
  --output-dir "$scratch/candidates" \
  > "$scratch/candidates.json"
for id in A B C D; do
  cmp "$solution/mystery-$id.txt" "$scratch/candidates/mystery-$id.txt"
done

for id in A B C D; do
  python3 "$solution/evaluator.py" --json \
    "$solution/mystery-$id.txt" \
    "$scratch/release/occam-circuit/datasets/mystery-$id/train.csv" \
    > "$scratch/training-$id.json"
done

python3 "$solution/run_controls.py" \
  --asset "$asset" \
  --results-root "$scratch/results"

python3 "$solution/generate_test_outputs.py" \
  --asset "$asset" \
  --output-dir "$scratch/predictions" \
  > "$scratch/predictions.json"
for id in A B C D; do
  cmp "$solution/predictions/mystery-$id/test_outputs.csv" \
    "$scratch/predictions/mystery-$id/test_outputs.csv"
done

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s "$solution/tests" -p 'test_*.py' -v
```

`run_controls.py` exercises both public practice circuits and the released
adder/public-training control with the independent Python evaluator. If Julia
is available, it also runs the released `verify.jl`; otherwise it records that
the official Julia control was unavailable.
