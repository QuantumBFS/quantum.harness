# Decoder-ready loss and reload data contract

The benchmark stores physical observations separately from final logical
labels. A future decoder can consume the input view without gaining access to
the answer or to future loss events.

## Input view

| Field | Type and shape | Meaning |
|---|---|---|
| `shot_id` | `int64[shots]` | Globally unique counter-addressed shot index |
| `detection_events` | `uint8[shots, detectors]` | Detector outcomes available to the decoder |
| `syndrome_valid_mask` | `uint8[shots, T, checks]` | Distinguishes a valid zero from a missing measurement |
| `missing_mask` | `uint8[shots, T+1, sites]` | Site unavailable at each start-of-round boundary |
| `reload_mask` | `uint8[shots, T+1, sites]` | Successful reload completion at a boundary |
| `revealed_events` | structured arrays | Loss detections, reload requests, failures and completions |
| `metadata` | manifest object | Geometry, basis, noise, policy, seed range and decoder version |

The decoder may read only information revealed at or before the current round.
Undetected/future loss, hidden Pauli events, holdout provenance and final labels
are forbidden inputs.

## Label view

| Field | Type and shape | Meaning |
|---|---|---|
| `logical_observable` | `uint8[shots, observables]` | Final logical measurement |
| `decoder_prediction` | `uint8[shots, observables]` | Baseline decoder output |
| `logical_failure` | `uint8[shots]` | Prediction differs from the logical observable |
| `catastrophic_loss` | `uint8[shots]` | Loss geometry crossed incompatible boundaries |

Labels live in a separately selected loader view. Label poisoning and removal
tests require the decoder prediction to remain bitwise unchanged.

## Boundary convention

For round `t`, `missing_mask[t]` is evaluated before syndrome extraction.
New losses are revealed only after that round. Reload completion at boundary
`t` restores a fresh carrier; it does not recover the unknown state carried by
the atom before loss. Boundary `T` records post-final-round occupancy without
erasing the earlier loss event.

## Storage and provenance

Each immutable run contains a versioned manifest, sharded NPZ arrays, Parquet
aggregates, a run log and `checksums.sha256`. The manifest binds the source
commit, locked environment, geometry ordering, request parameters, shot range,
Slurm identity and decoder implementation. The public PR includes compact
aggregate Parquet tables; large per-shot shards remain on the cluster and are
identified by their manifests.
