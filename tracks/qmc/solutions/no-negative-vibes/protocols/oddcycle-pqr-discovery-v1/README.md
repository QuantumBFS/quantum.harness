# Oddcycle `(p,q,r)` discovery scan v1

This protocol maps the fixed-point proof region of

`B(p,q,r)=[[0,0,2,0,0],[2,0,0,0,0],[0,2,0,p,0],`
`[0,0,0,1,q],[0,0,-r,0,1]]`

on a 2,744-cell Cartesian grid.  Each cell first runs the full numerical
exterior early-stop screen through depth 12 with the low-sector tail allowed
to start at depth 12.  Only exterior survivors with `p*q*r<8` reach the
convex common-metric SDP.

The scan is a discovery map.  A strict SDP metric removes a point as a known
split-contraction reduction.  A numerical zero-margin point is only a
survivor and requires an exact no-go.  The more promising next object is a
multi-point alphabet: distant individually sign-free points can fail to
share one metric even when each point separately has one.
