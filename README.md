# quantum.harness

> **Warning**
> This harness system is in a very early stage. Contributors are welcome, but
> the project is not ready for general users yet. A formal release is planned
> for August 2026.

A computational quantum research harness. It helps an AI agent to run the simulation of quantum systems.
Each method is curated by world-leading experts in that computational approach, so the guidance reflects real research practice: what to compute, which checks matter, and where common failures happen.

The Harness provides:
- **Model cards** with Hamiltonians, symmetries, etc
- **Numeric methods and tool-usage skills** with parameters setup guidance, computational resource estimation, and verification checks.
- **Supporting skills** for research survey, report writing, paper reproduction.
- **Cluster support** for calculations too large for a laptop.

<img alt="harness-c" src="https://github.com/user-attachments/assets/5b624046-099b-4743-8fee-ca39aa68b09b" />

## Start Here

If you do not yet have Claude Code, Codex CLI, or OpenCode installed, follow the [summer-school agent setup guide](https://giggleliu.github.io/summer-school-2026/guide#setup) first.

Paste this into Claude Code, Codex, or OpenCode:

```text
Clone https://github.com/QuantumBFS/quantum.harness.
Run `make skills` to install the harness skills.
Then run `/beginner-training` to start the guided training — pick a track and it walks you through, one confirmed step at a time.
```

## Numeric Methods for Quantum Systems

Each method is curated by world-leading experts in that computational approach.

| Method | Expert contributor | Skill |
|---|---|---|
| Exact diagonalization | [Chen Cheng (程晨)](https://scholar.google.com/citations?user=LZpS-T0AAAAJ) | `/method-ed` |
| MPS / LTRG / DMRG / TEBD | [Wei Li (李伟)](https://scholar.google.com/citations?user=7wiebe8AAAAJ) | `/method-mps` · `/method-ltrg` |
| PEPS / CTMRG | [Hai-Jun Liao (廖海军)](https://scholar.google.com/citations?user=_8KbQtEAAAAJ) | `/method-peps` |
| Quantum Monte Carlo | [Ming-Pu Qin (秦明普)](https://scholar.google.com/citations?user=ikqa-0IAAAAJ) | `/method-qmc` |
| Monte Carlo renormalization group | [Yan-Tao Wu (武琰涛)](https://scholar.google.com/citations?user=D8sgaMwAAAAJ) | `/method-mcrg` |
| Quantum circuit simulation | [Shi-Xin Zhang (张士欣)](https://scholar.google.com/citations?user=Ut8nVqIAAAAJ) | `/method-qcs` |
| AI agent and knowledge base | [Kun Chen (陈锟)](https://scholar.google.com/citations?user=YItDGoIAAAAJ), [Jin-Guo Liu (刘金国)](https://scholar.google.com/citations?user=4edw228AAAAJ) | [`tracks/agent-kb`](tracks/agent-kb/) |

## Example Prompts

```text
I want to reproduce Figure 2 of arXiv:1711.03528,
the PXP quantum many-body scars paper.
Use /reproduce-paper to guide me.
```

```text
/solve ground state of the J1-J2 Heisenberg model
on a 6x6 square lattice at J2/J1=0.5
```

```text
Survey recent work on neural quantum states
for frustrated magnets.
Use /survey to build a reference library.
```

## More

- [`.knowledge/`](.knowledge/) - model, physics, method, benchmark, and literature cards.
- [`skills/`](skills/) - agent workflows invoked as `/name`.
- [Harnessing Quantum 2026 submission guide](https://giggleliu.github.io/summer-school-2026/zh/guide) - for summer-school participants.
- [`AGENTS.md`](AGENTS.md) - full harness operating instructions.
