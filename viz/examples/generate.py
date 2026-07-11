#!/usr/bin/env python3
"""Deterministically regenerate the example scenes, preview.html, and the
report fixture. Stdlib only; seeded LCG so re-runs never dirty git."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

_seed = 12345
def rand():
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 0x7FFFFFFF


def square_j1j2(L=6):
    nodes, edges = [], []
    for y in range(L):
        for x in range(L):
            s = 0.4 * (1 if (x + y) % 2 == 0 else -1)
            nodes.append({"id": x + L * y, "pos": [x, y, 0], "value": s,
                          "vector": [0, 0, s],
                          "group": "A" if (x + y) % 2 == 0 else "B"})
    for y in range(L):
        for x in range(L):
            i = x + L * y
            edges.append({"s": i, "t": (x + 1) % L + L * y, "type": "J1",
                          "wrap": x == L - 1, "value": -0.42})
            edges.append({"s": i, "t": x + L * ((y + 1) % L), "type": "J1",
                          "wrap": y == L - 1, "value": -0.42})
            if x < L - 1 and y < L - 1:
                edges.append({"s": i, "t": (x + 1) + L * (y + 1),
                              "type": "J2", "value": 0.21})
            if x < L - 1 and y > 0:
                edges.append({"s": i, "t": (x + 1) + L * (y - 1),
                              "type": "J2", "value": 0.21})
    return {
        "meta": {"title": f"{L}x{L} J1-J2 Heisenberg (PBC)"},
        "nodes": nodes, "edges": edges,
        "types": {"J1": {"color": "#4a6fa5", "width": 2},
                  "J2": {"color": "#c0504d", "width": 1, "dash": True}},
        "encode": {"nodes": {"colormap": "diverging", "domain": [-0.5, 0.5]},
                   "edges": {"colormap": "diverging", "domain": [-1, 1]}},
    }


def cubic(L=8):
    import math
    nodes, edges = [], []
    idx = lambda x, y, z: x + L * (y + L * z)
    for z in range(L):
        for y in range(L):
            for x in range(L):
                v = math.sin(2 * math.pi * x / L) * math.cos(2 * math.pi * y / L) \
                    * math.cos(math.pi * z / L)
                nodes.append({"id": idx(x, y, z), "pos": [x, y, z],
                              "value": round(v, 4)})
    for z in range(L):
        for y in range(L):
            for x in range(L):
                i = idx(x, y, z)
                if x < L - 1: edges.append({"s": i, "t": idx(x + 1, y, z), "type": "t"})
                if y < L - 1: edges.append({"s": i, "t": idx(x, y + 1, z), "type": "t"})
                if z < L - 1: edges.append({"s": i, "t": idx(x, y, z + 1), "type": "t"})
    return {"meta": {"title": f"{L}^3 simple cubic"},
            "nodes": nodes, "edges": edges,
            "types": {"t": {"color": "#7a8494", "width": 1}},
            "encode": {"nodes": {"colormap": "diverging"}}}


def mc_animation(L=20, nframes=40, sweeps_per_frame=8):
    """2D Ising metropolis at T=2.0 — real coarsening dynamics, seeded."""
    import math
    N = L * L
    spins = [1 if rand() < 0.5 else -1 for _ in range(N)]
    T = 2.0
    frames, labels = [], []
    for f in range(nframes):
        for _ in range(sweeps_per_frame * N):
            i = int(rand() * N) % N
            x, y = i % L, i // L
            nn = (spins[(x + 1) % L + L * y] + spins[(x - 1) % L + L * y]
                  + spins[x + L * ((y + 1) % L)] + spins[x + L * ((y - 1) % L)])
            dE = 2 * spins[i] * nn
            if dE <= 0 or rand() < math.exp(-dE / T):
                spins[i] = -spins[i]
        frames.append(list(spins))
        labels.append(f"sweep {f * sweeps_per_frame}")
    nodes = [{"id": i, "pos": [i % L, i // L, 0]} for i in range(N)]
    edges = []
    for y in range(L):
        for x in range(L):
            i = x + L * y
            if x < L - 1: edges.append({"s": i, "t": i + 1, "type": "nn"})
            if y < L - 1: edges.append({"s": i, "t": i + L, "type": "nn"})
    return {"meta": {"title": f"{L}x{L} Ising Metropolis quench, T=2.0"},
            "nodes": nodes, "edges": edges,
            "types": {"nn": {"color": "#c8cdd4", "width": 0.5}},
            "encode": {"nodes": {"colormap": "diverging", "domain": [-1, 1]}},
            "frames": {"labels": labels, "nodes": frames}}


def peps(L=4):
    nodes, edges = [], []
    for y in range(L):
        for x in range(L):
            nodes.append({"id": f"T{x}{y}", "pos": [x, y, 0], "group": "tensor",
                          "label": f"A[{x},{y}]", "size": 1.4})
            nodes.append({"id": f"p{x}{y}", "pos": [x, y, -0.55], "virtual": True})
            edges.append({"s": f"T{x}{y}", "t": f"p{x}{y}", "type": "phys",
                          "label": "d=2"})
    for y in range(L):
        for x in range(L):
            if x < L - 1:
                edges.append({"s": f"T{x}{y}", "t": f"T{x+1}{y}", "type": "bond",
                              "label": "χ=8"})
            if y < L - 1:
                edges.append({"s": f"T{x}{y}", "t": f"T{x}{y+1}", "type": "bond",
                              "label": "χ=8"})
    return {"meta": {"title": f"{L}x{L} PEPS", "labels": "always"},
            "nodes": nodes, "edges": edges,
            "types": {"bond": {"color": "#4a6fa5", "width": 2},
                      "phys": {"color": "#8892a0", "width": 1}}}


SCENES = {"square-j1j2": square_j1j2(), "cubic": cubic(),
          "mc-animation": mc_animation(), "peps-diagram": peps()}

PREVIEW = """<!doctype html>
<html><head><meta charset="utf-8"><title>lattix preview</title>
<style>body{font:14px system-ui;max-width:900px;margin:24px auto;padding:0 12px}
h2{margin:28px 0 8px}</style></head><body>
<h1>lattix examples — eyeball gate</h1>
%s
<script src="../dist/lattix.min.js"></script>
<script>Lattix.mountAll();</script>
</body></html>
"""

def main():
    blocks = []
    for name, scene in SCENES.items():
        (HERE / f"{name}.json").write_text(
            json.dumps(scene, ensure_ascii=False) + "\n")
        payload = json.dumps(scene, ensure_ascii=False).replace("</", "<\\/")
        blocks.append(f'<h2>{name}</h2>\n<div class="lattix" data-height="420">'
                      f'<script type="application/json">{payload}</script></div>')
    (HERE / "preview.html").write_text(PREVIEW % "\n".join(blocks))

    fixture = HERE / "report-fixture"
    fixture.mkdir(exist_ok=True)
    (fixture / "scene.json").write_text(
        json.dumps(SCENES["square-j1j2"], ensure_ascii=False) + "\n")
    (fixture / "report.json").write_text(json.dumps({
        "title": "Lattix report fixture",
        "sections": [{"title": "Interactive views", "blocks": [
            {"kind": "lattice3d", "src": "scene.json",
             "caption": "Interactive. $6\\times 6$ J1-J2 lattice with PBC."},
            {"kind": "lattice3d", "src": "scene.json",
             "caption": "Second view — the JS bundle must appear only once."},
            {"kind": "lattice3d", "src": "missing.json",
             "caption": "Deliberately missing scene."},
        ]}]}, indent=1) + "\n")
    print("wrote", ", ".join(f"{n}.json" for n in SCENES),
          "preview.html report-fixture/")

if __name__ == "__main__":
    main()
