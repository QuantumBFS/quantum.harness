# Novelty and claim boundary

## Principal claim

For any finite loopless multigraph with arbitrary nonnegative inhomogeneous edge activities, and any vertex `v`, the generating polynomial of the random set of selected edges incident to `v` is multiaffine and real stable. Therefore the incident-edge marginal is strongly Rayleigh.

The theorem also holds after any feasible **coordinate conditioning** on edges outside the star (some prescribed present, some prescribed absent). It does not claim preservation under conditioning on an arbitrary non-coordinate event.

## Main new mechanism

For a weighted graph `K`, component parameter `q >= 0`, and vertex variables `x`, the manuscript proves

    Phi_{K,q}(x)
      = prod_{ij in E(K)} (1 - q y_ij partial_i partial_j)
        det(q I + L_K + diag(x)),

where

    Phi_{K,q}(x)
      = sum_{F forest} y^F prod_{C component of F} (q + sum_{u in C} x_u).

The coefficientwise cancellation is called **differential unrooting**. Each factor of the operator preserves multiaffine real stability by the Borcea-Brändén algebraic-symbol criterion.

## Consequences

- Negative association among disjoint groups of incident edges.
- Negative correlation of every pair of adjacent edges for arbitrary inhomogeneous nonnegative activities.
- The same local conclusions after feasible exterior coordinate conditioning.
- The number of selected edges in any subset of a star is Poisson-binomial; its rank sequence is ultra log-concave and its variance is at most its mean.

## Explicit non-claims

- The manuscript does **not** prove negative correlation for disjoint edges.
- It does **not** prove that the full forest measure is strongly Rayleigh; a triangle is already a counterexample to global real stability.
- It does **not** settle the general graphic independent-set Rayleigh conjecture.
- The earlier low-cyclomatic-number theorem is not presented as a principal novelty, because its conclusion is substantially covered by prior small-regular-matroid results plus 2-sum closure.

## Prior-art positioning

The introduction distinguishes the result from:

- the general weighted negative-correlation/Rayleigh problem for graphic matroid independent sets;
- Huang's adjacent-edge theorem for a common activity in a sufficiently large-activity regime;
- the general strong-Rayleigh theory and the known determinantal stability of spanning-tree measures;
- recent broader polynomial classes such as Gårding polynomials.

The current search found no direct predecessor for either the full arbitrary-weight incident-edge marginal theorem or the exact differential-unrooting identity. This is a reasoned novelty assessment, not a guarantee; a specialist search in MathSciNet/zbMATH and direct expert feedback are still required.
