# Publish the PRB paper and expose its location

## Goal

Publish the existing PRB-format PDF in the team solution directory and make
its canonical repository location immediately discoverable from both the team
README and pull request #222.

## Design

The verified PDF will be tracked at:

`tracks/qmc/solutions/卧龙凤雏/effective-central-charges-prb-paper.pdf`

The team README will gain a short `Paper` section containing a relative link
to that file. The pull-request description will retain its existing team and
challenge information and add a `Paper` section with a GitHub link to the same
path on the challenge branch.

The existing copy under `output/pdf/` remains unchanged. The two files have
identical SHA-256 content, so this change improves discoverability without
changing the scientific artifact.

## Verification

- Confirm both PDF copies have the same SHA-256 digest.
- Confirm the README relative link resolves to the tracked PDF.
- Push the commit to the PR source branch.
- Read PR #222 from GitHub and confirm its description contains the paper
  path and the PDF appears in the PR file list.
