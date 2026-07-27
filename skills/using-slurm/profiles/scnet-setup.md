# SCNet — provisioning SSH access

Companion to `scnet.toml`. SCNet (https://www.scnet.cn/, 国家超算互联网) issues
per-account SSH credentials through its web console; nothing here can be
automated by the agent, so walk the user through it one step at a time.

## 1. Get credentials from the SCNet console (user does this)

1. Log in at https://www.scnet.cn/ and open the cluster's command-line page
   (命令行 / E-Shell).
2. Click **SSH连接** (SSH Connection). It reveals the personal **host address,
   port, and username**.
3. Pick a validity period from the dropdown and **download the private key**.

Docs: https://www.scnet.cn/help/docs/mainsite/hpc/cmd/connect-to-hpc/

## 2. Install the key (user runs; agent cannot reach ~/Downloads on macOS)

macOS TCC blocks agent processes from reading `~/Downloads` — the user must
move the key themselves, either from their own prompt with the `!` prefix or
via Finder:

```bash
mv ~/Downloads/<downloaded-key-file> ~/.ssh/scnet_key
chmod 600 ~/.ssh/scnet_key
```

## 3. Add the alias (agent writes this)

Append to `~/.ssh/config`, filling the three console values. The alias must be
`scnet` to match `connection.ssh.alias` in `scnet.toml`:

```
Host scnet
    HostName <host address from console>
    Port <port from console>
    User <username from console>
    IdentityFile ~/.ssh/scnet_key
```

## 4. Verify

```bash
ssh -o BatchMode=yes scnet 'echo ok && hostname'
```

Expect `ok` and a login-node name (e.g. `zz-login01`). A warning like
`server gave bad signature for RSA key 0: error in libcrypto` is harmless —
the connection proceeds over the ED25519 host key (see the gotcha in
`scnet.toml`).

## Known shape of a working setup

- Key: `~/.ssh/scnet_key` (0600)
- Alias: `scnet` → an `*.scnet.cn` E-Shell host on a high, per-account port
- Remote repo: `~/quantum.harness` (clone on first ship; login node has
  internet)
