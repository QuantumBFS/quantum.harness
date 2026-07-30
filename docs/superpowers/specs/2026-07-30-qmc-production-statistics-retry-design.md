# Issue 147 QMC Production Statistics Retry Design

## Trigger

The equilibrated pilot completed all twelve cells and passed the split-half
and Trotter-fit gates. Its M=32 chains had R-hat 1.071, above the predeclared
1.05 gate, despite split-half z below 1.82 and lag-one correlations from 0.19
to 0.33. This is finite chain-to-chain sampling spread rather than visible
continued drift. The pilot remains diagnostic evidence and is not promoted to
the final QMC reference.

## Chosen retry

Run a complete new twelve-cell protocol named `issue147-qmc-production`.
Keep beta=0.5, h=3, M=32/64/128, four chains, the Wolff kernel, the estimator,
and 80 bins. Increase measurement cluster flips from 8000 to 32000 so each bin
contains 400 flips. Use thermalization counts 4000, 4000, and 16000 for
M=32, 64, and 128. The extra M=32 thermalization is cheap and removes the only
remaining marginal setup choice.

The completed pilot took 12-19 seconds per cell and less than 100 MiB, so the
fourfold measurement budget remains far inside the ratified ten-minute,
4-GiB cell request.

## Interface and acceptance

Add an optional `--measure-sweeps` QMC CLI override and pass merged run-spec
settings through the dispatcher. Existing runs retain the configured default.
The runtime manifest records the effective measurement count.

Apply the unchanged acceptance protocol: 8-bin chain-stratified block
bootstrap, split-half z no larger than 3, four-chain R-hat no larger than 1.05,
and reduced chi-squared below 4 for the linear fit in `(beta/M)^2`.
