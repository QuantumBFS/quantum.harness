# SCNet seccomp validator gate: jobs 6760453 and 6760456

## First run: 6760453

The first contract run failed with exit code `1:0`. The kernel filter itself
was active (`Seccomp: 2`) and an `AF_INET` socket creation returned `EPERM`.
The evidence collector incorrectly required the `NoNewPrivs` field in
`/proc/self/status`, which this Linux 3.10 kernel does not expose. No physics,
validator acceptance condition, or sandbox restriction was relaxed.

## Corrected run: 6760456

The corrected collector reads `no_new_privs` using
`prctl(PR_GET_NO_NEW_PRIVS)`. Job `6760456` completed with exit code `0:0` in
34 seconds. All 10 discovery/development-validator contract tests passed,
including the child-process proof that:

- `PR_GET_NO_NEW_PRIVS` returns 1;
- `/proc/self/status` reports seccomp mode 2;
- creating an IPv4 stream socket fails with `EPERM`;
- the same seccomp filter and 16 GiB address-space limit are installed in
  every candidate process before `exec`;
- the score aggregator rejects runner reports without exact sandbox evidence.

The batch step used 126,472 KiB MaxRSS. This establishes the network-denial
part of the fallback validator isolation. It does not by itself satisfy the
full validator gate: executable negative controls and a passing baseline
development matrix are still required.

```text
c6dc86bea6722a115ce9e7428916aa107ed08db7a164f1906e82f58bfd916a9a  test-discovery-contract-6760456.out
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  test-discovery-contract-6760456.err
```
