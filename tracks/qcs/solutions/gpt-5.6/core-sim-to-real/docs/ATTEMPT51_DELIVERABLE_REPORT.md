# Attempt 51 — queries-to-target deliverable

## Purpose

Challenge 113 explicitly requests queries-to-target versus search dimension.
This deliverable derives that figure from sealed Attempt-44 development and
Attempt-49 confirmation evidence. It makes no new simulator or device query,
does not tune a method, and does not alter either archived result.

## Metric

For each finite-shot run:

- if an accepted pulse first reaches exact post-hoc infidelity `<= 1e-3`, use
  the number of black-box queries and shots consumed at that accepted step;
- otherwise charge the complete frozen query and shot cap;
- average four nested shot-noise replicates within each truth cell; and
- compute a family-stratified truth-cell bootstrap interval.

This is a restricted-mean, post-hoc oracle-scored benchmark metric. It is not
available to the optimizer online. Attempt 43's online stopping certificate
failed and remains a negative result.

## Fresh confirmation values

| Method | Search dimension | Queries to target (95% CI) | Shots to target | Success |
|---|---:|---:|---:|---:|
| model-informed `k=15` | 15 | 48.76 [45.35, 52.47] | 1,563,061 | 90.625% |
| completed model-informed `k=40` | 40 | 160.62 [153.69, 165.84] | 5,207,808 | 25.000% |
| raw-coordinate `k=40` | 40 | 166.00 [166.00, 166.00] | 5,376,000 | 0.000% |

The development panel supplies the requested dimension sweep over
`k = 5, 10, 15, 20, 40`; the confirmation panel tests the selected `k=15`
method against the two frozen `k=40` comparators on fresh truths.

## Claim boundary

- Development selects the dimension; it is not confirmation evidence.
- Confirmation uses 24 independent truth cells with four nested replicates.
- Hidden exact values are attached only after each calibration client closes.
- The online stopping rule did not pass and is not revived by this plot.
- Failures remain in the metric at their complete frozen cap.
