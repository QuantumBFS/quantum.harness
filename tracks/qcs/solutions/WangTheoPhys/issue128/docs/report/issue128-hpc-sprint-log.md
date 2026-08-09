# Issue 128 六小时 HPC 冲刺运行记录

记录日期：2026-07-31（Asia/Shanghai）

## 冻结主张

本轮计算不覆盖既有认证结果。当前唯一可对外报告的倍率仍为
`11791/2911 = 4.050498110614909...`，对应 `r=393 → r=97`。除非新的完整全局误差账本及 fast/deep verifier 同时通过，否则不得把 D8 分项结果宣传为新的整体倍率。

## 可复现源状态

- 本地分支：`codex/issue128-hpc-six-hour`
- 生产源提交：`e65c95f4ae76dc1a78e81715cac21cfd7a81dbf8`
- 远端入口：`xh5-acamtw`
- 远端仓库：`/work/home/acamtw70yu/quantum-harness-issue128-hpc`
- Slurm account/QOS/partition：`giggleliu` / `user_acamtw70yu` / `xhacnormalb`
- 计算类型：CPU 上的 Python 精确整数/有理数与稀疏 Pauli 字典；GPU 不适用。

## 快速门槛

- Python 文件通过 `py_compile`。
- 坐标无关制品、确定性 gzip、manifest 与损坏拒绝测试：3 passed。
- 本地 stage 30 / order 8 smoke 成功，重复制品哈希稳定。
- 本地常规测试：93 passed，11 deselected，41.12 秒。
- 本地 deep verifier：`valid=true`，`deep_proof_regenerated=true`。
- 远端 smoke：作业 `23044170`，stages 28--30 完成且 manifest/hash 正常；stage 27 用作较重梯度检查。

## 生产图

| 角色 | Slurm job | 资源/上限 | 依赖 |
|---|---:|---|---|
| 31-stage exact D8 array | `23044178` | 每单元 17 CPU、64 GiB、4:30:00 | 无 |
| deep verifier + 全测试 | `23044196` | 9 CPU、32 GiB、4:30:00 | 无 |
| exact reducer | `23044212` | 26 CPU、96 GiB、1:15:00 | `afterok:23044178` |

数组最初以 16 路并发启动；确认账号/QOS允许后，用 Slurm 正常调度接口把 `ArrayTaskThrottle` 提升到 31。所有剩余单元随后进入 RUNNING；调度和授权仍由集群控制器执行。

## 制品契约

每个 `stage-XX` 目录包含：

- `shard.json.gz`：坐标寻址、registry 无关、canonical JSON、确定性 gzip；
- `manifest.json`：stage/order、开始结束时间、wall time、峰值 RSS、term counts、源提交、dirty 标志和 SHA-256；
- Slurm stdout/stderr：启动与完成状态。

归并器要求 31 个 manifest 全部成功、公式 ID/order/source commit 一致、每个 shard 哈希匹配，并要求正向与反向精确归并得到相同字典。任何失败均不得生成倍率主张。

## 终局判定

1. 若数组和 reducer 完成：读取 exact D8 site-density upper，重建 `r=78` 的完整 D4--D8+账本，再运行 fast/deep verifier。
2. 若任一 stage OOM/timeout：保留成功制品和 sacct 证据，按失败类别只重提缺失单元，不把部分和当全局界。
3. 若完整账本 `≤10⁻⁶`：可以进入五倍候选复核；仍需独立证书、报告和 fresh-clone 重现。
4. 若完整账本 `>10⁻⁶`：报告严格负结果与缺口，主倍率保持 4.050498×。
