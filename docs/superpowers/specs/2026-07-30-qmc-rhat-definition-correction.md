# Issue 147 QMC R-hat Definition Correction

The first acceptance implementation computed four-chain R-hat after reducing
each chain's 80 saved bins to ten 8-bin block means. That is not the standard
R-hat input and keeps the effective draw count fixed at ten even when each bin
contains more Monte Carlo updates. The resulting diagnostic did not stabilize
when the trajectories were extended.

R-hat is therefore computed from the 80 saved bin means in each chain. The
8-bin contiguous blocks remain unchanged for the chain-stratified bootstrap
and split-half drift test, where accounting for short-range autocorrelation is
the intended purpose. The R-hat threshold remains 1.05; no observed samples or
fit points are removed.
