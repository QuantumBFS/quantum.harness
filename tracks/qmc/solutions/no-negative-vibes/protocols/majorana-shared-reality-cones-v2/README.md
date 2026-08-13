# Majorana cones with a shared reality structure v2

This protocol repeats the v1 grid with a numerically stable direct Spin-trace
oracle. The Fock-space product is rescaled by a positive norm after each time
slice, which preserves its sign and phase. The determinant-square identity is
still checked, but an ill-conditioned `I + product exp(A_l)` is explicitly
flagged instead of treating its unstable floating-point determinant as ground
truth.

The candidate and grid are otherwise unchanged:

- two Majorana reflection-positive cones share the same `J1` reality
  structure;
- their `J2` contraction directions differ by a fixed angle;
- successive time slices alternate between the two cones;
- 4 and 6 Majoranas, depths through 16, four scales, eight angles, four seeds;
- 1,792 cells and 448,000 direct Fock traces.

An exact depth-two negative certificate for the opposite-cone endpoint is
stored in `fixtures/majorana_trace_certificates.json`; its weight is
`2 - 2 cosh(1) < 0`.
