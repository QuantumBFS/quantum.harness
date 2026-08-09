# Erratum for the frozen short technical report

Date recorded: 2026-07-31 (Asia/Shanghai)

## Scope

The six-page short report and the reviewer README frozen at commit
`ebb055926302c7d911e5ab00805513c382ac458d` contain a legacy auxiliary table
for recursive Suzuki orders 2, 4, 6, and 8. That table does not agree with the
authoritative schema-v3 main certificate.

The affected legacy values are:

```text
269,677; 36,361; 83,101; 377,251 merged groups
```

The authoritative values stored in
`certificates/issue128-certificate.json` under
`published_recursive_suzuki_audit` are:

| Recursive order | Steps | Stages per step | Merged groups | Error upper summary |
|---:|---:|---:|---:|---:|
| 2 | 29,964 | 7 | 179,785 | `9.9999203748666826e-7` |
| 4 | 808 | 31 | 24,241 | `9.9682621337975879e-7` |
| 6 | 370 | 151 | 55,501 | `9.8463753882538689e-7` |
| 8 | 335 | 751 | 251,251 | `9.9829085642259163e-7` |

## Authority rule

For exact numerical claims, the JSON certificate and its SHA-256-bound
sidecars are authoritative. The old short-report table is retained unchanged
so that the frozen manifest remains reproducible; it must not be cited as
current evidence. The long-form manuscript uses the schema-v3 values.

## Impact on the principal result

There is no impact on the certified result. The auxiliary recursive-order
audit is not used to derive any of the following primary quantities:

- pinned control: 393 steps and 11,791 merged groups;
- accepted candidate: 97 steps and 2,911 merged groups;
- adjacent boundary: 97 accepted and 96 rejected;
- exact resource ratio: `11791/2911 = 4.050498110614909...`;
- D4 partition: 75,324 terms in 7,576 verified groups.

The primary quantities remain bound to the unchanged main certificate with
SHA-256
`0a09623ce3b292a3637065c870fb3153bbdcddce30aef968565c4db3ddfc7201`.
