# Small-angle Majorana two-cone stress test v1

The broad v2 scan found no negative samples at relative angle `0.2`, and no
negative 6-Majorana samples at angle `0.4`. This targeted protocol tests
whether those zero-hit cells reflect only insufficient generator scale and
product depth.

- 4 and 6 Majoranas;
- relative angles `0.05,0.1,0.2,0.3,0.4`;
- depths through 32;
- generator scales `3,4,6`;
- four seeds and 300 products per cell;
- 840 cells and 252,000 direct Fock traces.

Large-scale determinant-square checks are expected to become ill-conditioned;
they are diagnostic only. The primary weight is the directly evaluated,
positively rescaled Fock trace. Negative samples close the corresponding
fixed-angle universal claim. Zero hits do not establish a protected angular
neighborhood.
