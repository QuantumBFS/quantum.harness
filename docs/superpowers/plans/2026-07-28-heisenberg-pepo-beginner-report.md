# Heisenberg-picture PEPO Beginner Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the existing PEPO method report with formulas and portable text diagrams that explain the Heisenberg-picture PEPO algorithm to a first-time tensor-network reader.

**Architecture:** Replace only Section 3 of the existing report with seven progressively connected explanations: picture change, operator inner product, PEPO representation, gate update and SVD, reverse light cone, scalar contraction, and a three-qubit example. Preserve every numerical result and conclusion outside that section.

**Tech Stack:** Markdown, Unicode mathematics, fenced `text` diagrams, Python consistency checks, Git whitespace checks.

## Global Constraints

- Modify only `tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_METHOD_REPORT_NOTE.md`.
- Use Unicode formulas; do not use dollar-delimited LaTeX or Mermaid.
- Use `Dop` only for operator-evolution virtual bonds and `χenv` only for final compressed-contraction intermediate bonds.
- Keep `C=Gₘ⋯G₂G₁` and traverse gates in the order `Gₘ,Gₘ₋₁,…,G₁`.
- Keep `F=2⁻ᴺ Tr[O C†OC]`.
- Preserve all existing measured values, resource data, result tables, and the conclusion that the PEPO result is not internally converged.

---

### Task 1: Replace the method overview with the beginner derivation

**Files:**
- Modify: `tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_METHOD_REPORT_NOTE.md:78-116`
- Reference: `tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/engine.py`
- Reference: `tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/contraction.py`

**Interfaces:**
- Consumes: the report's definitions `O=Z52 Z59 Z72`, `O_H=C†OC`, `F=2⁻ᴺTr[O O_H]`.
- Produces: a self-contained Section 3 whose notation is reused unchanged by Sections 4–12.

- [ ] **Step 1: Record the invariant part of the report**

Run:

```bash
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

text = Path(
    "tracks/qcs/solutions/CCB-LV.999/issue-119-ole/"
    "PEPO_METHOD_REPORT_NOTE.md"
).read_text()
prefix = text.split("## 3. 方法思路", 1)[0]
suffix = text.split("## 4. 参数定义", 1)[1]
print("prefix", sha256(prefix.encode()).hexdigest())
print("suffix", sha256(suffix.encode()).hexdigest())
PY
```

Save both hashes in the work log. They guard Sections 1–2 and 4–12
byte-for-byte.

- [ ] **Step 2: Replace Section 3**

Use `apply_patch` to replace lines 78–116 with these seven subsections:

1. `3.1 从 Schrödinger picture 到 Heisenberg picture`
2. `3.2 OLE 是两个算符的内积`
3. `3.3 PEPO 怎样表示一个多体算符`
4. `3.4 量子门怎样更新 PEPO`
5. `3.5 反向光锥怎样减少工作量`
6. `3.6 怎样把 PEPO 收缩成 OLE`
7. `3.7 三量子比特例子与完整流程`

The inserted content must include:

```text
|ψout⟩ = C|ψin⟩
⟨ψout|O|ψout⟩ = ⟨ψin|C†OC|ψin⟩
```

```text
(A,B)HS = 2⁻ᴺ Tr[A†B]
F = (O,O_H)HS = 2⁻ᴺ Tr[O C†OC]
```

```text
O_H ≈ Σ_{s,s′,{α}}
      [∏ᵢ Aᵢ(sᵢ′,sᵢ; {αᵢⱼ})]
      |s₁′…sN′⟩⟨s₁…sN|
```

```text
Θ′ = Gᵢⱼ† Θ Gᵢⱼ = U S V†
   ≈ Σₐ₌₁ᴰᵒᵖ sₐ uₐvₐ†
```

```text
Qₖ ∩ S = ∅  → skip
Qₖ ∩ S ≠ ∅ → keep, S ← S ∪ Qₖ
```

```text
F(Dop,χenv) = 2⁻ᴺ Contract[PEPO_Dop(O_H) × O]
```

Include four portable text figures:

- Schrödinger versus Heisenberg flow;
- one PEPO tensor and a three-site PEPO;
- merge/gate/SVD/truncate/split for a two-site gate;
- the complete QASM-to-`F` pipeline.

Define dagger, physical leg, virtual leg, operator entanglement, Hilbert–Schmidt inner product, `Dop`, and `χenv` on first use. State that the chain and grid figures illustrate indices only; the actual PEPO follows the QASM CZ interaction graph.

- [ ] **Step 3: Verify the gate order and contraction formula against code**

Run:

```bash
rg -n \
  'for index in range\\(len\\(gates\\) - 1|gate_dagger|math\\.ldexp\\(1\\.0, -nsites\\)|max_bond=chi_env' \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/engine.py \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo/src/ole_pepo/contraction.py
```

Expected:

- reverse traversal starts at the last recorded gate;
- the applied array is conjugate-transposed;
- normalization is `2⁻ᴺ`;
- compressed contraction uses `max_bond=chi_env`.

- [ ] **Step 4: Verify required concepts and diagram count**

Run a Python read-only check that asserts:

- all seven subsection headings occur exactly once;
- the strings `Hilbert–Schmidt`, `operator entanglement`, `physical leg`,
  `virtual leg`, `Dop`, and `χenv` occur in Section 3;
- Section 3 has at least four fenced `text` blocks containing diagram
  connectors such as `──`, `│`, or `→`;
- no dollar-delimited LaTeX, `TODO`, or `TBD` appears.

Expected: `errors=0`.

- [ ] **Step 5: Confirm that no result text changed**

Re-run:

```bash
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

text = Path(
    "tracks/qcs/solutions/CCB-LV.999/issue-119-ole/"
    "PEPO_METHOD_REPORT_NOTE.md"
).read_text()
prefix = text.split("## 3. 方法思路", 1)[0]
suffix = text.split("## 4. 参数定义", 1)[1]
print("prefix", sha256(prefix.encode()).hexdigest())
print("suffix", sha256(suffix.encode()).hexdigest())
PY
```

Expected: both hashes exactly match Step 1.

- [ ] **Step 6: Run Markdown checks**

Run:

```bash
git diff --check -- \
  tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_METHOD_REPORT_NOTE.md
```

Expected: exit 0 with no trailing whitespace or malformed patch output.

- [ ] **Step 7: Commit only the report change**

```bash
git add tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_METHOD_REPORT_NOTE.md
git commit -m "docs: explain Heisenberg PEPO workflow"
```
