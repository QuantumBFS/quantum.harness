# SCNet validator negative controls: job 6760472

Job `6760472` completed with exit code `0:0` in 15 seconds. All four
executable control candidates were rejected by their intended guard:

- `wrong-answer` emitted structurally valid, checksummed artifacts, but exact
  replay rejected the changed `decoder_prediction` array.
- `cheater` used a one-seed lookup and returned code 23 for the generated
  unseen seed.
- `timeout` spawned child PID 9212. The two-second deadline terminated the
  process group with return code -15, and `/proc/9212` no longer existed.
- `env-escape` received `EPERM` when creating a socket and wrote into its
  copied candidate source. The before/after source-tree hashes differed, so
  the source mutation guard rejected it.

The batch step used 98,968 KiB MaxRSS.

```text
740b519b0b3ff73f63b69e131c708381fabbfa3c30297ed4d5bdfe75c55e74d3  results/validator/negative-controls/6760472/report.json
a23938bf837075edb76a1912b71e936400190b924a3f91e2accd1db01c033a47  test-negative-controls-6760472.out
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  test-negative-controls-6760472.err
```
