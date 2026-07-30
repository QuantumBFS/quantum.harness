#!/usr/bin/env python3
"""Generate Berry curvature figures for Challenge 73 final report."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

outdir = 'figures'

# ====== Data from Challenge 73 Final Report ======

# Table 1: Berry curvature density vs Omega for L=2,3,4
omega_vals = np.array([1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0])
f_l2 = np.array([-0.1755, -0.1437, -0.1000, -0.0601, -0.0367, -0.0233, -0.0109])
f_l3 = np.array([-0.1296, -0.1855, -0.1673, -0.0907, -0.0429, -0.0221, -0.0080])
f_l4 = np.array([-0.1282, -0.1478, -0.1914, -0.1330, -0.0479, -0.0205, -0.0067])

# Critical region detail
omega_crit = np.array([2.544, 3.044, 3.544])
f_l2_crit = np.array([-0.0905, -0.0543, -0.0334])
f_l3_crit = np.array([-0.1531, -0.0780, -0.0372])
f_l4_crit = np.array([-0.1848, -0.0803, -0.0303])

# 1/L extrapolation: Omega = 3.5, 4.0, 5.0
invL = np.array([1/2, 1/3, 1/4])
f_extrap = {
    3.5: [-0.0367, -0.0429, -0.0479],
    4.0: [-0.0233, -0.0221, -0.0205],
    5.0: [-0.0109, -0.0080, -0.0067],
}

# ====== Figure 1: Berry curvature density vs Omega ======
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

ax1.plot(omega_vals, f_l2, 'o-', label='L=2 (N=4)', color='#e41a1c', ms=6, lw=1.2)
ax1.plot(omega_vals, f_l3, 's-', label='L=3 (N=9)', color='#377eb8', ms=6, lw=1.2)
ax1.plot(omega_vals, f_l4, '^-', label='L=4 (N=16)', color='#4daf4a', ms=6, lw=1.2)
ax1.axhline(y=0, color='gray', ls=':', lw=0.8)
ax1.axvline(x=3.044, color='gray', ls='--', lw=0.8, alpha=0.5)
ax1.set_xlabel(r'$\Omega/J$', fontsize=13)
ax1.set_ylabel(r'$\bar{F}_{\theta\Omega}$', fontsize=13)
ax1.legend(fontsize=11)
ax1.set_title('Full range', fontsize=13)

# Merge main data and critical-region data for zoom
all_omega = np.sort(np.concatenate([omega_vals, omega_crit]))
all_f2 = np.array([f_l2[np.where(omega_vals == o)[0][0]] if o in omega_vals 
                    else f_l2_crit[np.where(omega_crit == o)[0][0]] for o in all_omega])
all_f3 = np.array([f_l3[np.where(omega_vals == o)[0][0]] if o in omega_vals
                    else f_l3_crit[np.where(omega_crit == o)[0][0]] for o in all_omega])
all_f4 = np.array([f_l4[np.where(omega_vals == o)[0][0]] if o in omega_vals
                    else f_l4_crit[np.where(omega_crit == o)[0][0]] for o in all_omega])

ax2.plot(all_omega, all_f2, 'o-', label='L=2', color='#e41a1c', ms=5, lw=1)
ax2.plot(all_omega, all_f3, 's-', label='L=3', color='#377eb8', ms=5, lw=1)
ax2.plot(all_omega, all_f4, '^-', label='L=4', color='#4daf4a', ms=5, lw=1)
ax2.axvline(x=3.044, color='gray', ls='--', lw=0.8, alpha=0.5)
ax2.set_xlabel(r'$\Omega/J$', fontsize=13)
ax2.set_ylabel(r'$\bar{F}_{\theta\Omega}$', fontsize=13)
ax2.legend(fontsize=10)
ax2.set_title('Including critical-region detail', fontsize=13)
ax2.set_xlim(1.5, 5.5)
ax2.set_ylim(-0.22, 0.02)

plt.tight_layout(pad=1.5)
fig.savefig(f'{outdir}/c73_berry_curvature_vs_omega.png',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Saved: {outdir}/c73_berry_curvature_vs_omega.png")

# ====== Figure 2: Thermodynamic limit extrapolation ======
fig, ax = plt.subplots(figsize=(7, 5.5))
colors = ['#e41a1c', '#377eb8', '#4daf4a']

for i, (omega, y) in enumerate(f_extrap.items()):
    coeffs = np.polyfit(invL, y, 1)
    fn = np.poly1d(coeffs)
    x_fine = np.linspace(0, 0.55, 50)
    ax.plot(invL, y, 'o', color=colors[i], ms=8, label=rf'$\Omega={omega}$')
    ax.plot(x_fine, fn(x_fine), '-', color=colors[i], alpha=0.5, lw=1.2)
    ax.plot(0, fn(0), 'D', color=colors[i], ms=10,
            markeredgecolor='#333333', markeredgewidth=0.6)

ax.set_xlabel(r'$1/L$', fontsize=14)
ax.set_ylabel(r'$\bar{F}_{\theta\Omega}$', fontsize=14)
ax.legend(fontsize=12, loc='lower left', framealpha=0.9)
ax.set_title(r'Thermodynamic limit: $1/L$ extrapolation', fontsize=14)
ax.axhline(y=0, color='gray', ls=':', lw=0.8)
ax.set_xlim(-0.02, 0.55)

plt.tight_layout()
fig.savefig(f'{outdir}/c73_tl_extrapolation.png',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Saved: {outdir}/c73_tl_extrapolation.png")

print("Done.")
