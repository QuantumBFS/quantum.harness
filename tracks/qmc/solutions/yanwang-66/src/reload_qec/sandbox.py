"""Linux process sandbox primitives used by the SCNet validator."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import resource
import subprocess
from pathlib import Path
from typing import Any


SANDBOX_SCHEMA = "q66-candidate-sandbox-v2"
MAX_ADDRESS_SPACE_BYTES = 16 * 1024**3

_AUDIT_ARCH_X86_64 = 0xC000003E
_X32_SYSCALL_BIT = 0x40000000
_PR_SET_NO_NEW_PRIVS = 38
_PR_SET_SECCOMP = 22
_SECCOMP_MODE_FILTER = 2
_SECCOMP_RET_KILL = 0x00000000
_SECCOMP_RET_ERRNO = 0x00050000
_SECCOMP_RET_ALLOW = 0x7FFF0000

_BPF_LD = 0x00
_BPF_W = 0x00
_BPF_ABS = 0x20
_BPF_JMP = 0x05
_BPF_JEQ = 0x10
_BPF_JGE = 0x30
_BPF_K = 0x00
_BPF_RET = 0x06

# Linux x86-64 syscall numbers. Blocking socket creation plus every direct
# network operation prevents both INET and UNIX-domain communication. Blocking
# process-group changes keeps inherited descendants inside the validator's
# killable process group until the candidate phase has ended.
_DENIED_SYSCALLS_X86_64 = (
    41,   # socket
    42,   # connect
    43,   # accept
    44,   # sendto
    45,   # recvfrom
    46,   # sendmsg
    47,   # recvmsg
    48,   # shutdown
    49,   # bind
    50,   # listen
    51,   # getsockname
    52,   # getpeername
    53,   # socketpair
    54,   # setsockopt
    55,   # getsockopt
    109,  # setpgid
    112,  # setsid
    288,  # accept4
    299,  # recvmmsg
    307,  # sendmmsg
)


class SandboxError(RuntimeError):
    """Raised when the required candidate sandbox cannot be established."""


class _SockFilter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("jt", ctypes.c_ubyte),
        ("jf", ctypes.c_ubyte),
        ("k", ctypes.c_uint32),
    ]


class _SockFprog(ctypes.Structure):
    _fields_ = [
        ("len", ctypes.c_ushort),
        ("filter", ctypes.POINTER(_SockFilter)),
    ]


def _statement(code: int, value: int) -> _SockFilter:
    return _SockFilter(code=code, jt=0, jf=0, k=value)


def _jump(code: int, value: int, jt: int, jf: int) -> _SockFilter:
    return _SockFilter(code=code, jt=jt, jf=jf, k=value)


def install_candidate_sandbox() -> None:
    """Install an inherited seccomp network denylist and hard resource limits."""

    if os.uname().machine != "x86_64":
        raise SandboxError("candidate seccomp filter only supports x86_64")
    denied = _SECCOMP_RET_ERRNO | errno.EPERM
    instructions = [
        _statement(_BPF_LD | _BPF_W | _BPF_ABS, 4),
        _jump(_BPF_JMP | _BPF_JEQ | _BPF_K, _AUDIT_ARCH_X86_64, 1, 0),
        _statement(_BPF_RET | _BPF_K, _SECCOMP_RET_KILL),
        _statement(_BPF_LD | _BPF_W | _BPF_ABS, 0),
        _jump(_BPF_JMP | _BPF_JGE | _BPF_K, _X32_SYSCALL_BIT, 0, 1),
        _statement(_BPF_RET | _BPF_K, _SECCOMP_RET_KILL),
    ]
    for syscall_number in _DENIED_SYSCALLS_X86_64:
        instructions.extend(
            (
                _jump(_BPF_JMP | _BPF_JEQ | _BPF_K, syscall_number, 0, 1),
                _statement(_BPF_RET | _BPF_K, denied),
            )
        )
    instructions.append(_statement(_BPF_RET | _BPF_K, _SECCOMP_RET_ALLOW))
    instruction_array = (_SockFilter * len(instructions))(*instructions)
    program = _SockFprog(len(instructions), instruction_array)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise SandboxError(
            f"PR_SET_NO_NEW_PRIVS failed: {os.strerror(error_number)}"
        )
    if (
        libc.prctl(
            _PR_SET_SECCOMP,
            _SECCOMP_MODE_FILTER,
            ctypes.byref(program),
            0,
            0,
        )
        != 0
    ):
        error_number = ctypes.get_errno()
        raise SandboxError(f"seccomp filter failed: {os.strerror(error_number)}")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_AS,
        (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES),
    )


_PREFLIGHT = """
import ctypes
import errno
import json
import os
import socket

PR_GET_NO_NEW_PRIVS = 39
status = {}
with open('/proc/self/status', encoding='ascii') as handle:
    for line in handle:
        if line.startswith('Seccomp:'):
            status['seccomp_mode'] = int(line.split()[1])
libc = ctypes.CDLL(None, use_errno=True)
libc.prctl.restype = ctypes.c_int
status['no_new_privs'] = libc.prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError as exc:
    status['socket_errno'] = exc.errno
else:
    status['socket_errno'] = 0
try:
    os.setsid()
except OSError as exc:
    status['setsid_errno'] = exc.errno
else:
    status['setsid_errno'] = 0
try:
    os.setpgid(0, 0)
except OSError as exc:
    status['setpgid_errno'] = exc.errno
else:
    status['setpgid_errno'] = 0
print(json.dumps(status, sort_keys=True))
raise SystemExit(0 if status == {
    'no_new_privs': 1,
    'seccomp_mode': 2,
    'setpgid_errno': errno.EPERM,
    'setsid_errno': errno.EPERM,
    'socket_errno': errno.EPERM,
} else 1)
"""


def network_denial_preflight(python_executable: str | Path) -> dict[str, Any]:
    """Prove inherited network and process-group escape denial."""

    try:
        process = subprocess.run(
            [str(python_executable), "-c", _PREFLIGHT],
            check=False,
            capture_output=True,
            text=True,
            preexec_fn=install_candidate_sandbox,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        raise SandboxError(f"network-denial preflight could not run: {exc}") from exc
    if process.returncode != 0:
        raise SandboxError(
            "network-denial preflight failed: "
            f"return_code={process.returncode}, stdout={process.stdout!r}, "
            f"stderr={process.stderr!r}"
        )
    try:
        observed = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise SandboxError("network-denial preflight returned invalid JSON") from exc
    return {
        "schema_version": SANDBOX_SCHEMA,
        "network_isolation": "seccomp-bpf-errno-eperm",
        "process_group_isolation": "seccomp-bpf-errno-eperm",
        "no_new_privs": observed.get("no_new_privs"),
        "seccomp_mode": observed.get("seccomp_mode"),
        "setpgid_errno": observed.get("setpgid_errno"),
        "setsid_errno": observed.get("setsid_errno"),
        "socket_errno": observed.get("socket_errno"),
        "address_space_limit_bytes": MAX_ADDRESS_SPACE_BYTES,
    }
