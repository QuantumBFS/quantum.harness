# Public issue #133 live campaign

This directory publishes five **new** tensor-network problems.  It does not
count the historical #124--#128 calibration set.

Every item contains a frozen challenge, a separately preregistered executable
gate, a Solver certificate, a fresh Verifier subprocess receipt, a rejected
negative control, and a human acceptance decision from `human.junkaiwang`
acting as `human expert supervision`.

Run from the repository root:

```bash
python3 tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign/run_campaign.py
python3 -m unittest discover \
  -s tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign/tests -v
```

Verify all published bytes:

```bash
cd tracks/agent-kb/solutions/WangTheoPhys/issue133-campaign
shasum -a 256 -c SHA256SUMS.txt
```

See [`REPORT.md`](REPORT.md) for the five-row acceptance/solve table and
[`artifacts/campaign.json`](artifacts/campaign.json) for the machine-readable
evidence graph.

The submission reports `5 / 5` supervised human acceptances and `5 / 5`
exact solved gates.  QuantumBFS maintainers retain final catalog and tier
authority.  Refereed publications remain `0`.
