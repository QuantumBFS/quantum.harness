# Occam's Circuit — recover a hidden logic function from polynomially many examples

Challenge issue (discussion, updates, Day-5 reveal): **https://github.com/QuantumBFS/quantum.harness/issues/71**

## The task

Each dataset comes from a **hidden Boolean function** $f:\{0,1\}^{2n}\to\{0,1\}^m$: the input bitstring encodes two $n$-bit integers $x$ and $y$; the output encodes an arithmetic function of them (perhaps $x+y$, perhaps $x\cdot y$, perhaps $x^2+y^2$, perhaps something else). You see only polynomially many samples — as little as 3% of the truth table. Astronomically many functions fit the training data perfectly and disagree everywhere else; the problem is ill-posed **unless you demand the simplest explanation**.

**Find the smallest circuit consistent with `train.csv`, then predict the outputs for `test_inputs.csv`.** Leaderboard order: (1) exact-match accuracy on the hidden test outputs, (2) fewer gates breaks ties. Memorizing the training set is easy — and will bomb the test set. That is the point.

## Quick start

```sh
julia verify.jl adder8.txt datasets/mystery-A/train.csv
# gates:            37  (inverters free)
# exact-match acc:  1.0
# bit accuracy:     1.0
```

`adder8.txt` is an example circuit in the required format — a textbook ripple-carry adder. It fits mystery-A's training data perfectly with 37 gates. Coincidence? Your call.

## Files

| Path | Meaning |
|---|---|
| `datasets/<instance>/train.csv` | `input,output` bitstring pairs — your only training signal |
| `datasets/<instance>/test_inputs.csv` | inputs you must predict |
| `datasets/<instance>/commitment.sha256` | SHA-256 of the withheld `test_outputs.csv` (also anchored in issue #71 — goalposts are frozen) |
| `generate.jl` | dataset generator, for making your own practice instances |
| `verify.jl` | circuit simulator / scorer (Julia stdlib only) |

Practice instances (`practice-add-n4` = $x+y$, `practice-mul-n4` = $x\cdot y$) have disclosed ground truth so you can calibrate your pipeline. The four **mystery** instances hide the function; difficulty is *not* ordered A→D:

| Instance | input bits $2n$ | output bits $m$ | train | test | observed fraction |
|---|---|---|---|---|---|
| mystery-A | 16 | 9 | 2000 | 2000 | 3.1% |
| mystery-B | 14 | 7 | 1500 | 2000 | 9.2% |
| mystery-C | 12 | 12 | 1200 | 1500 | 29% |
| mystery-D | 10 | 11 | 400 | 624 | 39% |

## Encoding

Input = $2n$ characters: the $n$ bits of $x$ followed by the $n$ bits of $y$, both **LSB-first** (character $i$ of a block is bit $i-1$). Output = $m$ characters, LSB-first. Example for $n=4$: input `10110010` splits into x-block `1011` (LSB-first → $x = 1+4+8 = 13$) and y-block `0010` (→ $y = 4$). Decode carefully — endianness bugs are the classic trap here.

## Circuit format

Plain text, one statement per line, `#` comments. Fanin-2 gates from `AND OR XOR NAND NOR XNOR`; inverters (`~`) are **free** and allowed on any operand or output:

```
INPUTS 16
w1 = XOR x1 x9
w2 = AND x1 x9
w3 = XOR ~w1 x2
OUTPUTS w1 w3 ...
```

Inputs are `x1..x2n` (same order as the dataset input string); wires must be defined before use; **score = number of gate lines**.

## Why this is hard (and interesting)

- Occam's razor is a theorem: returning a *near-minimum* consistent hypothesis guarantees generalization (Blumer–Ehrenfeucht–Haussler–Warmuth 1987).
- Finding it is NP-hard: this problem is partial MCSP (Hirahara, FOCS 2022). Bring heuristics: DMRG-style tensor-network completion (a circuit *is* a tensor network; MPS ≅ BDD, arXiv:2505.01930), BDD learning with variable reordering, SAT/MILP exact synthesis, logic-synthesis tools (ABC/espresso), or an LLM agent that guesses the semantic function and then synthesizes it — recognizing structure IS the game.
- Difficulty is theorem-backed: addition-like functions have linear-size minimal representations; multiplication needs exponential BDDs for *any* variable ordering (Bryant 1991).
- It is the discrete, explicit-razor cousin of grokking (Power et al. 2022, arXiv:2201.02177).

## Submitting

Standard fork & PR model: work under `tracks/qcs/solutions/<your-team>/` in your fork of [QuantumBFS/quantum.harness](https://github.com/QuantumBFS/quantum.harness). Include your circuits (`mystery-*.txt`), predicted `test_outputs.csv` per mystery instance, committed search scripts, and a pitch-style README explaining your method and what you believe each hidden function is. Generated data goes to the gitignored `results/`.

Test outputs are revealed on Day 5; verify them against `commitment.sha256`.
