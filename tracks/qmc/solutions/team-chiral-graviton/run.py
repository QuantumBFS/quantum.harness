"""
Main entry point for the chiral graviton NQS calculation.

Usage:
    python run.py --mode ground --n_elec 6 --steps 2000
    python run.py --mode excited --n_elec 6 --steps 2000
    python run.py --mode full --n_elec 6 --steps 2000
    python run.py --mode test_symmetry --n_elec 6
    python run.py --mode ed_check --n_elec 4
"""

import argparse
import torch
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.haldane_sphere import HaldaneSphere, device, dtype_real
from src.ansatz import FullWavefunction
from src.hamiltonian import Hamiltonian
from src.sampler import SphereSampler
from src.vmc import VMCOptimizer
from src.excitations import sma_gap, L2ExcitedState
from src.utils import print_header, print_results, bootstrap_error


def parse_args():
    parser = argparse.ArgumentParser(
        description="Symmetric NQS for chiral graviton in FQH"
    )
    parser.add_argument("--mode", type=str, default="full",
                        choices=["ground", "excited", "full",
                                 "test_symmetry", "ed_check"],
                        help="Calculation mode")
    parser.add_argument("--n_elec", type=int, default=6,
                        help="Number of electrons")
    parser.add_argument("--steps", type=int, default=2000,
                        help="VMC optimization steps")
    parser.add_argument("--hidden_dim", type=int, default=64,
                        help="Neural network hidden dimension")
    parser.add_argument("--n_layers", type=int, default=3,
                        help="Neural network depth")
    parser.add_argument("--lr", type=float, default=0.1,
                        help="Learning rate")
    parser.add_argument("--n_samples", type=int, default=512,
                        help="Samples per VMC step")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--use_minSR", action="store_true", default=True,
                        help="Use minSR optimizer")
    return parser.parse_args()


def run_ground_state(args):
    """Optimize the ground state (L=0)."""
    print_header(f"Ground State Calculation: N={args.n_elec} electrons at nu=1/3")

    # Initialize
    sphere = HaldaneSphere(args.n_elec)
    print(f"  Flux 2Q = {sphere.two_Q}, nu = {sphere.N}/{sphere.two_Q} = 1/3")
    print(f"  Sphere radius R = {sphere.R:.4f} l_B")

    wf = FullWavefunction(args.n_elec, args.hidden_dim,
                          args.n_layers, use_minSR=args.use_minSR)
    print(f"  Neural network parameters: {wf.count_params():,}")
    print(f"  Device: {device}")

    ham = Hamiltonian(sphere)
    sampler = SphereSampler(args.n_elec, step_size=0.15)

    vmc = VMCOptimizer(wf, ham, sampler, lr=args.lr,
                       use_minSR=args.use_minSR)

    # Training loop
    print(f"\n  Training for {args.steps} iterations...")
    energy_history = vmc.train(
        args.steps,
        n_samples=args.n_samples,
        n_warmup=20,
        n_thin=3,
        verbose=True
    )

    # Final result
    final_energy = energy_history[-1] if energy_history else 0.0
    n_iter = len(energy_history)
    window = max(1, n_iter // 10)
    avg_energy = sum(energy_history[-window:]) / window
    std_energy = (sum((e - avg_energy) ** 2 for e in energy_history[-window:])
                  / max(window - 1, 1)) ** 0.5

    print(f"\n  Final energy: E(L=0) = {avg_energy:.6f} +/- {std_energy:.6f}")

    results = {
        "N (electrons)": args.n_elec,
        "Flux 2Q": sphere.two_Q,
        "E(L=0) [e^2/(epsilon l_B)]": avg_energy,
        "Error bar": std_energy,
        "Iterations": n_iter,
        "Final accept rate": f"{sampler.accept_rate:.1%}",
        "Final |dtheta|": vmc.grad_norm_history[-1] if vmc.grad_norm_history else 0,
    }
    print_results(results)

    return wf, sphere, results


def run_excited_state(args, wf_gs=None, sphere=None):
    """Compute the L=2 excitation energy."""
    print_header(f"Excited State (L=2) Calculation: N={args.n_elec}")

    if sphere is None:
        sphere = HaldaneSphere(args.n_elec)

    if wf_gs is None:
        print("  No ground state provided. Loading from checkpoint...")
        wf_gs = FullWavefunction(args.n_elec, args.hidden_dim,
                                 args.n_layers, use_minSR=args.use_minSR)
        try:
            checkpoint = torch.load(f"checkpoint_gs_N{args.n_elec}.pt",
                                    map_location=device, weights_only=True)
            for name, param in wf_gs.named_parameters():
                if name in checkpoint['model_state'] and param.requires_grad:
                    param.data.copy_(checkpoint['model_state'][name])
            print("  Checkpoint loaded.")
        except FileNotFoundError:
            print("  No checkpoint found. Using untrained ground state.")
    else:
        print("  Using provided ground state wavefunction.")

    ham = Hamiltonian(sphere)
    sampler = SphereSampler(args.n_elec, step_size=0.12)

    # Method 1: Single-mode approximation
    print("\n  Computing SMA estimate...")
    try:
        sma_results = sma_gap(wf_gs, sphere, sampler,
                              n_samples=2048, n_warmup=200)
        print(f"  SMA gap estimate: {sma_results.get('Delta_SMA_estimate', 'N/A')}")
    except Exception as e:
        print(f"  SMA computation failed: {e}")
        sma_results = {}

    # Method 2: Variational excited state
    print("\n  Setting up variational L=2 excitation...")
    excited = L2ExcitedState(wf_gs, sphere)

    # Sample from ground state for overlap check
    theta_s, phi_s, xyz_s, _, _, accept = sampler.sample(
        wf_gs, args.n_samples, n_warmup=50, n_thin=3
    )
    print(f"  Sampling accept rate: {accept:.1%}")

    # Compute gap with current parameters
    # Note: For a full calculation, the excited state would be
    # optimized separately with the L=2 constraint
    delta, E0, E2 = excited.compute_gap(
        theta_s.unsqueeze(0), phi_s.unsqueeze(0),
        xyz_s.unsqueeze(0), ham
    )

    print(f"\n  E(L=0) = {E0:.6f}")
    print(f"  E(L=2) = {E2:.6f}")
    print(f"  Δ = E(L=2) - E(L=0) = {delta:.6f}")

    # Compute L^2 expectation (should be 6 for pure L=2)
    L2_val = excited.project_L2(xyz_s, theta_s, phi_s)
    print(f"  ⟨L²⟩ = {L2_val:.4f} (expected 6 for L=2)")

    # Overlap check
    overlap_val = excited.overlap(
        theta_s.unsqueeze(0), phi_s.unsqueeze(0), xyz_s.unsqueeze(0)
    )
    print(f"  |⟨Ψ_ex|Ψ_gs⟩| = {overlap_val:.4f} (should be ~0)")

    results = {
        "N (electrons)": args.n_elec,
        "E(L=0) [e^2/(epsilon l_B)]": E0,
        "E(L=2) [e^2/(epsilon l_B)]": E2,
        "Delta [e^2/(epsilon l_B)]": delta,
        "<L^2> on excited": L2_val,
        "Overlap |<ex|gs>|": overlap_val.item(),
    }
    results.update(sma_results)
    print_results(results)

    return results


def test_symmetry(args):
    """Test SO(3) equivariance of the ansatz."""
    print_header(f"Symmetry Test: N={args.n_elec}")

    sphere = HaldaneSphere(args.n_elec)
    wf = FullWavefunction(args.n_elec, args.hidden_dim, args.n_layers)

    # Generate a test configuration
    theta, phi, xyz = sphere.sample_initial(1, seed=0)

    # Compute log-psi for original configuration
    log_psi_orig = wf(theta, phi, xyz)
    print(f"  Original: log|Psi| = {log_psi_orig.real.item():.6f}, "
          f"arg = {log_psi_orig.imag.item():.6f}")

    # Apply random SO(3) rotation
    from scipy.spatial.transform import Rotation as R
    r = R.random()
    rot_matrix = torch.tensor(r.as_matrix(), device=device, dtype=dtype_real)

    xyz_rot = torch.matmul(xyz, rot_matrix.T)
    theta_rot = torch.acos(xyz_rot[..., 2].clamp(-1, 1))
    phi_rot = torch.atan2(xyz_rot[..., 1], xyz_rot[..., 0])
    phi_rot = phi_rot % (2 * math.pi)

    # Compute log-psi for rotated configuration
    log_psi_rot = wf(theta_rot, phi_rot, xyz_rot)
    print(f"  Rotated:  log|Psi| = {log_psi_rot.real.item():.6f}, "
          f"arg = {log_psi_rot.imag.item():.6f}")

    # For an SO(3)-equivariant ansatz, |Psi|² should be invariant
    prob_orig = torch.exp(2 * log_psi_orig.real)
    prob_rot = torch.exp(2 * log_psi_rot.real)
    diff = (prob_orig - prob_rot).abs().item()
    print(f"\n  |Psi|² difference under rotation: {diff:.6e}")
    print(f"  SO(3) equivariance: {'PASS' if diff < 1e-4 else 'CHECK - possible violation'}")

    # Test permutations (electron exchange)
    perm = torch.randperm(sphere.N)
    theta_perm = theta[:, perm]
    phi_perm = phi[:, perm]
    xyz_perm = xyz[:, perm]

    log_psi_perm = wf(theta_perm, phi_perm, xyz_perm)

    # For fermions, a permutation should give sign change
    # but |Psi|^2 is invariant
    prob_perm = torch.exp(2 * log_psi_perm.real)
    diff_perm = (prob_orig - prob_perm).abs().item()

    n_swaps = sum(1 for i, j in enumerate(perm)
                  if j < i)  # rough parity
    expected_sign = (-1) ** (n_swaps % 2)
    phase_diff = (log_psi_perm.imag - log_psi_orig.imag).item() % (2 * math.pi)

    print(f"\n  |Psi|² under permutation: diff = {diff_perm:.6e}")
    print(f"  Expected fermion sign: {expected_sign}")
    print(f"  Phase change: {phase_diff:.4f}")
    is_antisymmetric = diff_perm < 1e-4 and abs(phase_diff - math.pi * (n_swaps % 2)) < 0.1
    print(f"  Antisymmetry: {'PASS' if is_antisymmetric else 'CHECK - see note'}")

    results = {
        "SO(3) diff": f"{diff:.2e}",
        "Permutation diff": f"{diff_perm:.2e}",
        "SO(3)": "PASS" if diff < 1e-4 else "WARNING",
        "Antisymmetry": "PASS" if is_antisymmetric else "WARNING",
    }
    print_results(results)
    return results


def ed_crosscheck(args):
    """Cross-check with exact diagonalization for small N."""
    print_header(f"Exact Diagonalization Cross-Check: N={args.n_elec}")

    from src.ed_crosscheck import (
        exact_ground_state_energy,
        exact_L2_energy,
        verify_5fold_degeneracy
    )

    try:
        E0, desc = exact_ground_state_energy(args.n_elec)
        print(f"  Ground state (L=0): E = {E0:.6f} ({desc})")

        E2, E0_2, Delta, desc2 = exact_L2_energy(args.n_elec)
        print(f"  Excited state (L=2): E = {E2:.6f} ({desc2})")
        print(f"  Neutral gap: Delta = {Delta:.6f}")

        degen = verify_5fold_degeneracy(args.n_elec)
        if degen["confirmed"]:
            print(f"  L=2 degeneracy: 5-fold ✓ (splitting {degen['splitting']:.2e})")
        else:
            print(f"  L=2 degeneracy: not available for N={args.n_elec}")

        results = {
            "N": args.n_elec,
            "E0 (exact)": E0,
            "E2 (exact)": E2,
            "Delta (exact)": Delta,
            "5-fold": degen["confirmed"],
        }
        print_results(results)
        return results

    except NotImplementedError as e:
        print(f"  {e}")
        print("  ED cross-check only available for N in {4, 6, 7, 8}.")
        return None


def main():
    args = parse_args()

    torch.manual_seed(args.seed)

    if args.mode == "ground":
        run_ground_state(args)

    elif args.mode == "excited":
        run_excited_state(args)

    elif args.mode == "full":
        print_header("Full Chiral Graviton Calculation Pipeline")
        print(f"N = {args.n_elec} electrons at nu = 1/3")
        print(f"Device: {device}")

        # Step 1: Ground state
        wf_gs, sphere, gs_results = run_ground_state(args)

        # Save checkpoint
        torch.save({
            'model_state': {name: p.data.clone()
                           for name, p in wf_gs.named_parameters()
                           if p.requires_grad},
            'energy_history': gs_results,
        }, f"checkpoint_gs_N{args.n_elec}.pt")

        # Step 2: Excited state
        ex_results = run_excited_state(args, wf_gs, sphere)

        # Step 3: ED cross-check
        ed_results = ed_crosscheck(args)

        # Summary
        print_header("Summary")
        print(f"\n  Chiral graviton gap at nu = 1/3, N = {args.n_elec}:")
        print(f"    E(L=0) = {gs_results.get('E(L=0) [e^2/(epsilon l_B)]', 0):.6f}")
        print(f"    E(L=2) = {ex_results.get('E(L=2) [e^2/(epsilon l_B)]', 0):.6f}")
        print(f"    Δ = {ex_results.get('Delta [e^2/(epsilon l_B)]', 0):.6f}")

    elif args.mode == "test_symmetry":
        test_symmetry(args)

    elif args.mode == "ed_check":
        ed_crosscheck(args)

    print("\nDone.")


if __name__ == "__main__":
    main()
