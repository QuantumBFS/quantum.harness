# 精确 TTN 的 GPU 集群迁移路线

## 当前已实现的阶段

收缩器现在有两条精确路径。小连接保留 NumPy 参考实现；达到 CUDA 阈值的
流式连接执行

```text
共享键编码
    → GPU 共享键排序与相等组计划（显存允许时）
    → 按精确 J_g = n_L(g)n_R(g) 前缀切片
    → 每张 GPU 在线程内收集并锁页传输自己的输入区间
    → CUDA 内核由贡献编号恢复组内 (i,j)
    → CUDA 内核直接生成反射规范化 key/value
    → GPU sort/reduce-by-key
    → 有序 run
```

因此主机不再为 CUDA 流式连接物化逐贡献的 `left_rows/right_rows`。每块的

```text
uint64 output_key / uint64 output_value
    → 按 key 排序
    → 对相同 key 做精确 uint64 求和
    → 严格递增的唯一 key/value run
```

抽象成独立的 `ExactBlockReducer`。

提供两个实现：

- `numpy`：CPU 参考实现，也是默认后端；
- `cuda`：可选 CuPy 实现，在 CUDA GPU 上执行 key/value 排序和
  reduce-by-key；传入多个设备时使用多 GPU 键范围分片。

此外已经实现：

- 预算预检产生的排序分组计划由流式路径直接复用，不再进行第二次排序；
- 八张卡各有一个在途组片，输入收集在对应 worker 线程内并行执行；
- H2D 输入和 D2H 归并结果使用 CUDA 锁页主存；
- GPU 内核融合组内配对、坐标解码、反射规范化和精确值生成；
- 小块自动回退 NumPy，大块才送入 GPU；
- 外部归并采用有限扇入的分层并行归并，不再一次打开数千个文件；
- 中间归并文件使用 partial 文件、原子改名和完成标记。

CUDA/CuPy 是可选依赖。CPU 环境不导入 CuPy，也不改变已有运行方式。请求
CUDA 但 CuPy或设备不可用时，程序会在收缩开始前明确报错。

当前仍未完成的是：超出单卡排序显存时的多 GPU/外存共享键分组、持久化
join-shard manifest、进程重启后的缺失 shard 重算，以及跨节点调度。因此它
已经是单节点多 GPU 的贡献生成器，但还不能称为完整的多节点收缩器。

## 为什么不能直接调用 GEMM

稠密张量收缩可以通过指标重排写成矩阵乘法。但本路线故意不物化稠密中间
张量：例如 \(N=15\) 的 rank-9 包络已有

\[
15^9=38\,443\,359\,375
\]

个格点，仅一个 `uint64` 稠密数组约 307 GB；rank-13 包络更不可行。因此实际
算子不是常规稠密 GEMM，而是

\[
\text{共享坐标等值连接}
\rightarrow\text{稀疏贡献生成}
\rightarrow\text{sort/reduce-by-key}.
\]

它更接近 GPU 数据库 join、radix sort、run-length encode 和 segmented
reduction。再加上系数必须保持精确 `uint64`，V100 的 FP16/FP32 Tensor Core
不能直接代替整数收缩。GPU 仍然适合这条路线，但需要面向稀疏连接设计 kernel，
而不是把不可承受的零元素补回去。

## 使用

CPU 参考后端：

```bash
python3 python/contract_symmetric_parity_ttn.py \
  --n-min 1 --n-max 11 \
  --join-chunk-pairs 1000000 \
  --block-reducer numpy
```

CUDA 节点上安装与集群 CUDA 运行时匹配的 CuPy 后：

```bash
CUDA_VISIBLE_DEVICES=0 \
python3 python/contract_symmetric_parity_ttn.py \
  --n-min 11 --n-max 11 \
  --join-chunk-pairs 4000000 \
  --streaming-merge-strategy sorted-runs \
  --block-reducer cuda \
  --cuda-device 0
```

单机四卡：

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 \
python3 python/contract_symmetric_parity_ttn.py \
  --n-min 11 --n-max 11 \
  --join-chunk-pairs 8000000 \
  --streaming-merge-strategy sorted-runs \
  --block-reducer cuda \
  --cuda-devices 0,1,2,3 \
  --cuda-min-records 1000000 \
  --cuda-records-per-device 2000000
```

`--cuda-device` 和 `--cuda-devices` 都使用 `CUDA_VISIBLE_DEVICES` 过滤后的
进程内编号；设备列表会覆盖单设备参数。输出 summary 新增：

- `block_reducer_backend`;
- `block_reducer_device`;
- `block_reducer_devices`;
- `block_reducer_calls`;
- `block_reducer_input_records`;
- `block_reducer_output_records`;
- `block_reducer_seconds`;
- `block_reducer_async_submissions`;
- `block_reducer_cpu_fallback_calls`;
- `block_reducer_cpu_fallback_records`;
- `block_reducer_gpu_device_dispatches`.

`--cuda-min-records` 以下的块走 NumPy 精确归并；
`--cuda-records-per-device` 控制一个块按贡献数最多激活多少张卡。二者只改变
执行位置，不改变连接记录或算术。

## 为什么仍然精确

GPU 后端只处理 `uint64` 键和值：

1. 按键重排记录；
2. 对相同键的值做整数加法；
3. 返回相同的严格递增唯一键。

它不使用浮点数，不丢弃记录，也不改变收缩树和对称轨道规则。在既有
\(N^N<2^{64}\) 安全界内，整数加法重结合不改变结果。CPU 参考后端保留为
逐节点和端到端回归基准。

## 当前多 GPU 算法

旧的内存内小连接仍可按输出键范围分给多张卡。新的流式主路径改为先按共享
键组的精确连接量做全局贡献编号，再切成近似等长的工作片。每个工作片保留
组起点、左右计数和组内起始偏移，不携带逐贡献行号。于是：

- 八张卡按贡献数而不是输出键跨度取得工作；
- 巨大单组也能从组内偏移处分块；
- 每张卡独立生成和局部 reduce-by-key；
- 不同卡可能产生相同输出键，所以有序 run 最后做精确外部归并。

源张量当前仍在主机或 mmap 文件中；worker 只收集自己组片覆盖的连续排序
区间，再通过锁页内存传输。后续需要把常用输入 shard 驻留 GPU/NVMe 并加入
NUMA 绑定，才能进一步减少 PCIe 和主机 gather 成本。

## 8×V100 实测

服务器为 8 张 Tesla V100-SXM2 32 GB。所有结果使用相同的精确张量网络、
`uint64` 算术和拓扑计划。

| 实验 | 旧实现 | 融合 CPU | 自适应 8 GPU |
|---|---:|---:|---:|
| N=11 完整收缩 | 约 19.4 s（剖析运行） | 14.34 s | 5.34 s |
| N=11 块归并 | 2.50–3.52 s | 2.57 s | 1.04 s |
| N=12 完整收缩 | — | — | 29.64 s |
| N=15 同预算部分收缩 | 149.90 s | — | 95.16 s |
| N=15 块归并 | 19.74 s | — | 12.97 s |

新 GPU 贡献内核的 N=11 运行得到精确标量 2680；N=12 得到 14200，并处理
最大 259,757,335 项的精确连接。N=12 使用 8M 贡献片、GPU 共享坐标编码、
锁页传输和 128 路直接归并。旧 N=15 两次运行都完成 111/120 个计划
节点，在同一个 1,150,580,209-pair 下一连接前按 332,706,850 的预算停止；
所以表中比较的是同一精确部分前沿，不是近似答案。N=15 进程峰值 RSS 从约
8.79 GB 变为约 8.76 GB，主要收益来自减少重复坐标读取、流水重叠和避免小块
过度多卡调度。

## 单 GPU 数据通路

当前 CUDA 流式路径已经去掉 CPU 生成的 `left_rows/right_rows`。对每个共享键组
\(g\)，计算

\[
J_g=n_L(g)n_R(g)
\]

以及组前缀和。GPU 线程根据贡献编号直接恢复

\[
i=\lfloor p/n_R(g)\rfloor,\qquad
j=p\bmod n_R(g),
\]

并直接生成输出键和值。目标流水线是：

```text
GPU shared-key encode
  → radix sort
  → run-length encode
  → 左右组 merge/intersection
  → 64-bit group prefix scan
  → fused pair contribution kernel
  → radix sort output key/value
  → reduce-by-key
  → host/SSD sorted run
```

这样每个连接不再额外物化两个 `uint32` 行号，可少用至少 8 字节临时空间。

## 完整多 GPU / 多节点 join 分解

单个收缩节点内部可按共享键组分片。协调进程先构造只含拓扑和组偏移的精确
manifest，再按预计连接量平衡分片：

```text
contraction node
  ├── shard 0: groups [g0, g1) → sorted run 0
  ├── shard 1: groups [g1, g2) → sorted run 1
  ├── ...
  └── shard m: groups [gm, end) → sorted run m
```

每个 GPU worker：

1. 只读取自己的左右组区间；
2. 生成全部匹配贡献；
3. 在本地 GPU 上排序和 reduce-by-key；
4. 写出带校验元数据的严格递增 run。

协调器等待所有 shard 完成，然后使用现有 C++ k 路归并器精确合并。不同 shard
可能产生相同输出键，所以最终全局归并不可省略。

分布式执行不把不同收缩树节点任意并行：父节点必须等待两个子张量完成。主要
并行度来自单个超大 join 内的共享键组分片，以及收缩 DAG 中确实彼此独立的
节点。

## 集群存储要求

GPU 集群版仍需要共享或分布式外存。中间张量采用两个顺序文件：

```text
keys.bin    little-endian uint64, strictly increasing
values.bin  little-endian uint64, same length
```

worker run 可写入节点本地 NVMe，随后分层归并：

1. GPU 内块归并；
2. 节点本地 run 归并；
3. 机架或作业级全局归并。

应避免让所有 GPU 同时随机访问一个共享网络文件。大张量输入宜按组索引和
连续行区间分片，并对热输入做节点本地缓存。

## 后续实施顺序

1. 已完成：可选单 GPU CUDA 块归并后端；
2. 已完成：单进程多 GPU 键范围块归并；
3. 已完成：CUDA 与 NumPy 在 8×V100 上做 N=11 端到端一致性测试；
4. 已完成：CPU/GPU 流水重叠和按块大小自适应设备调度；
5. 已完成：GPU fused pair contribution kernel，消除左右行号数组；
6. 部分完成：单卡可容纳时的 GPU shared-key sort 和连接预检；
7. 生成可重启、可校验的 join-shard manifest；
8. 已完成：单节点多 GPU join worker；
9. 部分完成：有限扇入的单节点并行 run 分层归并；
10. 检查点、失败 shard 重试和最终标量证书。

只有第 7 步以及跨节点 worker 完成后，程序才是真正的集群 join 分片版本。
当前已经支持单节点多 GPU 完整生成贡献，但不应宣传为跨机器分布式收缩。

## V100 与 A100 的部署建议

- V100 16/32 GB：从每个全局块 1–4 百万条贡献开始测量；
- A100 40/80 GB：从 4–16 百万条开始测量；
- 块大小是全部 GPU 合计的输入块，不是每卡各自再复制一份；
- 不要在同一个等范围池中混用 V100 与 A100，否则较慢设备可能成为同步点；
- 每个节点优先使用本地 NVMe 写 run，再做分层外存归并；
- 第一轮基准必须同时记录 GPU 利用率、PCIe/NVLink 传输、块归并时间和磁盘
  写入时间。

这些范围只是安全起始值，最终应根据实际显存、CuPy 排序工作区和键分布调整。
