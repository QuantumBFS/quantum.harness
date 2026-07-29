---
name: reuse-julia-daemon
description: Use when repeated local Julia commands suffer time-to-first-execution (TTFX), when the user asks for a persistent Julia process, DaemonMode.jl, a transparent Julia wrapper/shim, or reuse of compiled Julia code across agent shell calls. Configure and operate the opt-in quantum-harness Julia daemon only on trusted single-user workstations; never enable it on shared login or compute nodes.
---

# Reuse Julia daemon

Reduce repeated local Julia compilation latency with the harness's optional DaemonMode.jl runner. Keep the compute project unchanged and let ordinary compatible `julia --project=...` commands reuse a persistent process.

## Binding rules

- Use this only on a trusted, single-user local workstation. Never enable it on shared login nodes, compute nodes, containers shared by multiple users, or Slurm jobs; use ordinary Julia there.
- Treat installation of the PATH shim as a consequential user-level configuration change. Explain the effect and risks, then obtain explicit confirmation before running `make julia-daemon SHIM=1`.
- Keep DaemonMode in its dedicated cache tool environment. Never add it to `julia-env/Project.toml` or another compute project.
- Do not replace or edit a user's existing unmanaged `julia` executable. The installer rejects that case; surface the error instead of forcing replacement.
- A daemon retains compiled code, loaded modules, allocations, and global/task-local state. Warn that memory can grow to OOM and earlier state can affect later calls.
- Restart after dependency, environment, or substantial source changes. Stop after large or varied workloads to release memory.
- Do not claim that daemon reuse improves numerical runtime after compilation; it addresses repeated startup and compilation latency only.

## Workflow

1. **Confirm the symptom.** Establish that repeated independent local Julia invocations are paying TTFX. Do not enable the daemon merely because a calculation itself is slow.
2. **Check prerequisites.** Verify Julia works and the repository contains `scripts/julia-daemon.sh`. If Julia or `julia-env` is not ready, dispatch `/setup-julia` first.
3. **Propose for ratification.** State that the transparent shim keeps normal `julia --project=...` syntax but starts an unauthenticated localhost service and retains memory/state. Offer ordinary Julia as the escape hatch. Wait for explicit approval.
4. **Install.** For transparent agent use, run:

   ```bash
   make julia-daemon SHIM=1
   ```

   For an explicit runner without changing command resolution, run:

   ```bash
   make julia-daemon
   scripts/julia-daemon.sh run --project=julia-env -e 'println(getpid())'
   ```

5. **Verify command resolution.** Confirm the installed shim directory precedes the real Julia directory on `PATH`. Then run two compatible commands and verify they report the same PID:

   ```bash
   julia --project=julia-env -e 'println(getpid())'
   julia --project=julia-env -e 'println(getpid())'
   ```

   Also verify native fallback still works:

   ```bash
   julia --version
   ```

6. **Use normal Julia syntax.** Compatible `--project=<explicit-directory>` plus `-e` or `.jl` calls use the daemon. REPL, `--version`, `-J`, `--threads`, `--project=@.`, ambiguous options, and unsupported argument forms fall back to the real Julia executable.
7. **Reset when needed.** For an explicitly selected port, run:

   ```bash
   managed_port=3000
   scripts/julia-daemon.sh stop --port "$managed_port"
   ```

   If a transparent project-derived daemon must be reset and its port is not known, do not kill Julia processes manually. Inspect the runner's managed state under `${XDG_CACHE_HOME:-$HOME/.cache}/quantum-harness/julia-daemon/`, identify the matching project, and call `stop --port <managed-port>`; process identity checks must remain in control.

## Report

Report only:

- whether transparent shim or explicit runner was enabled;
- real Julia path and compute project used;
- whether two calls reused one PID and native fallback worked;
- the stop/restart warning for memory and stale state.

## Alternatives

This is deliberately a minimal TTFX workaround. For persistent workspace semantics, runtime introspection, debugging, semantic tools, or richer agent communication, consider `julia-mcp`, `Kaimon.jl`, or `KaimonSlate.jl` instead.
