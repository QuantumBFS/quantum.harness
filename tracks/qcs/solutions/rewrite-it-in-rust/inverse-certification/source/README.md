# Frozen Source Snapshot

These files are copied byte-for-byte from companion commit `22d1605` so the relation encoding and
proof-generation logic are publicly inspectable in this PR. Their build-tree destinations are:

| Snapshot | Build-tree destination |
|---|---|
| `inverse.rs` | `challenge-71-occam/src/inverse/mod.rs` |
| `cnf.rs` | `challenge-71-occam/src/synthesis/cnf.rs` |
| `relation.rs` | `challenge-71-occam/src/synthesis/relation.rs` |
| `proof.rs` | `challenge-71-occam/src/synthesis/proof.rs` |
| `occam_inverse_certify.rs` | `challenge-71-occam/src/bin/occam_inverse_certify.rs` |
| `relation_synthesis.rs` | `challenge-71-occam/tests/relation_synthesis.rs` |
| `inverse_proof_artifacts.rs` | `challenge-71-occam/tests/inverse_proof_artifacts.rs` |

The certificate is independently checkable without trusting this source: run the pinned
`drat-trim` command in the parent README against the committed DIMACS and DRAT files.
