# quantum.harness

A computational quantum research harness. It helps an AI agent to run the simulation of quantum systems.
Each method is curated by world-leading experts in that computational approach, so the guidance reflects real research practice: what to compute, which checks matter, and where common failures happen.

<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/30c5dc11-f7e8-4b15-a161-0e78ddfecfad" />


## What The Harness Provides

- Model and physics cards with Hamiltonians, conventions, phases, and known limits.
- Method cards with algorithm choices, setup guidance, and verification checks.
- Skills such as `/onboard`, `/reproduce-paper`, `/solve`, `/parameter-scan`, and `/survey`.
- Generated scripts under `scripts/` and outputs under `results/`.
- Cluster support for calculations too large for a laptop.


## Start Here

If you do not yet have Claude Code, Codex CLI, or OpenCode installed, follow the
[summer-school agent setup guide](https://giggleliu.github.io/summer-school-2026/guide#setup)
first.

Paste this into Claude Code, Codex, or OpenCode:

```text
Clone https://github.com/QuantumBFS/quantum.harness.
Run `make skills` to install the harness skills.
Then run `/track-starter` to help me understand a method by reproducing a paper.
```

## Numeric Methods for Quantum Systems

Each method is curated by world-leading experts in that computational approach. Each method folder contains the starting point for students, including the target problem, recommended stack, and verification expectations.

| Method | Expert contributor | Folder |
|---|---|---|
| Exact diagonalization | [Chen Cheng (程晨)](https://scholar.google.com/citations?user=LZpS-T0AAAAJ) | [`tracks/ed/`](tracks/ed/) |
| MPS / DMRG / TEBD | [Wei Li (李伟)](https://scholar.google.com/citations?user=7wiebe8AAAAJ) | [`tracks/mps/`](tracks/mps/) |
| PEPS / CTMRG | [Hai-Jun Liao (廖海军)](https://scholar.google.com/citations?user=_8KbQtEAAAAJ) | [`tracks/peps/`](tracks/peps/) |
| Quantum Monte Carlo | [Ming-Pu Qin (秦明普)](https://scholar.google.com/citations?user=ikqa-0IAAAAJ), [Kun Chen (陈锟)](https://scholar.google.com/citations?user=YItDGoIAAAAJ) | [`tracks/qmc/`](tracks/qmc/) |
| VMC / neural quantum states | [Yan-Tao Wu (武琰涛)](https://scholar.google.com/citations?user=D8sgaMwAAAAJ) | [`tracks/vmc/`](tracks/vmc/) |
| Quantum circuit simulation | [Shi-Xin Zhang (张士欣)](https://scholar.google.com/citations?user=Ut8nVqIAAAAJ), [Jin-Guo Liu (刘金国)](https://scholar.google.com/citations?user=4edw228AAAAJ) | [`tracks/qcs/`](tracks/qcs/) |

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
