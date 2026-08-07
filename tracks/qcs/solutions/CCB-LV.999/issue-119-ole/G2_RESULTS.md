# G2 baseline reproduction result

## 结论

49-qubit、648-CZ operator Loschmidt echo 的 BP-TN baseline 已按固定的
20-seed bank 在 χ=192 和 χ=512 上完成。两组结果均满足计划中的 G2
接受条件。

| χ | N | mean | SE | 95% CI | public reference | absolute difference | tolerance | accepted |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 192 | 20 | 0.8185618335 | 0.0019847196 | [0.8144077675, 0.8227158994] | 0.8202512915 | 0.0016894580 | 0.0059541589 | yes |
| 512 | 20 | 0.8183229132 | 0.0019858354 | [0.8141665120, 0.8224793144] | 0.8216584890 | 0.0033355758 | 0.0059575061 | yes |

接受规则为 `|mean − reference| ≤ max(0.002, 3 SE)`。

## Paired χ comparison

20 个 seed 使用完全相同的计算基初态。逐 seed 的
`χ512 − χ192` 全部为负：

- paired mean = −0.0002389203；
- paired SE = 0.0000065177；
- 95% paired CI = [−0.0002525621, −0.0002252785]；
- 最大绝对 paired difference = 0.0002807823。

因此 χ=192→512 的系统漂移远小于当前 N=20 的随机初态 SE；本轮 G2 的主要
不确定度是随机初态采样，而不是 χ 截断。

## Protocol and provenance

- QASM SHA-256:
  `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455`；
- active qubits: 49；layers: 73；CZ gates: 648；
- observable: `Z52 Z59 Z72`；
- `L=3`, `b=0.25`, `δ=0.15`；
- TensorNetworkQuantumSimulator.jl 0.4.4,
  commit `b5d4089849de1cc23806aa8325e8db56a55f2e0b`；
- ComplexF64, cutoff `1e-12`, BP tolerance `1e-8`；
- one Julia thread and 16 BLAS threads per cell；
- fixed seed namespace `issue119-ole-v1`, seeds 1–20。

`δ=0` 的 seed 1 control 在 χ=64 上严格返回 1.0，且最大 bond 仅为 32。
因为该 circuit 是严格的 `U` 后接 `U†`，本轮没有浪费资源把相同 identity
control 重复到全部 χ 和 seed。

## Resource evidence

运行目标为 `zyli@172.16.42.215` 的 Slurm `batch` 分区；没有使用 SCNet
或 bigmem。

| χ | mean wall | max wall | max RSS | max truncation | max BP residual |
|---:|---:|---:|---:|---:|---:|
| 192 | 120.2 s | 129.3 s | 2.37 GiB | 2.50e-4 | 4.40e-11 |
| 512 | 134.2 s | 162.0 s | 3.34 GiB | 9.99e-13 | 2.84e-16 |

全部 40 个结果均为 complete，BP non-converged layers 为 0。生产数组为
Slurm job 410814；χ=192/512 单点资源探针分别为 jobs 410808/410810。

## Decision

G2 baseline reproduce 已经完成，不再为本目标追加 χ=256/384 或重复 δ=0。
χ=256/384 paired set、扩大随机初态 N、以及更窄统计区间属于后续 G3
误差预算，而不是本次 baseline 接受条件。
