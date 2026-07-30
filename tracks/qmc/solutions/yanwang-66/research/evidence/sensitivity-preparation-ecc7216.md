# Cost-sensitivity execution preparation

Status: staged but not authorized for simulation. The frozen workflow forbids
cost-sensitivity execution until a discovery analysis reports
`status=final-discovery` and `next_phase_groups=0`.

The preparation adds a strict loader for the preregistered 48-group/192-cell
matrix. It rejects drift in group order, physical parameters, reload costs,
policy order, seeds, shot ranges, source/environment provenance, family hash,
and baseline references. The initial executor runs all cells in one Slurm
allocation, checks the exact frozen candidate tree before and after simulation,
exact-replays all 192 outputs, and atomically publishes 48 paired group
manifests plus root checksums.

```text
orchestration commit:
ecc7216c81e21ce9b4fe86477ce8e12adb8cc65b

orchestration tree:
f130e22de6c55814c9e9486c13b227579482eaf0

orchestration archive SHA-256:
ee2508f907433b440ed265d7e879c06c7a03cf97bda14464a22f8510131780db

orchestration snapshot:
bundle-sensitivity-ecc7216

orchestration snapshot manifest SHA-256:
34fab84305c120152b989399df96533bca60fe4822ed8c7a944256be4f2c943b

snapshot files covered by the manifest:
150

cost-sensitivity family SHA-256:
ff5fddd9b6019b06a61fe43e59c50fc385ec29921351ff815a2d7d233affa900

accepted candidate tree SHA-256:
829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482
```

The published snapshot is read-only and all 150 manifest entries passed on
SCNet. It remains a candidate until its focused contracts pass inside the
eventual gated sensitivity allocation. No local Python, simulation, validator,
or analysis was run during preparation.
