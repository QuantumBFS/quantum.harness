# N 皇后精确 TTN / 多 GPU 交付包

版本日期：2026-07-30

本包把技术路线 PDF 与其对应的程序源码放在一起。主实现使用约束张量网络的精确收缩，并逐层加入紧凑数组、打包键、列反射宇称分块、行反射基本域、对称收缩树、磁盘流式归并和多 GPU 分块。它不以逐解枚举或配置动态规划作为求解算法。

## 目录

- `docs/nqueens_exact_ttn_gpu_cluster_technical_route_zh.pdf`：完整中文技术路线。
- `docs/TECHNICAL_ROUTE_EXACT_TTN_NQUEENS.md`：底层逻辑和理论说明。
- `docs/GPU_CLUSTER_ROUTE.md`：V100/A100 与多卡运行说明。
- `docs/REPORT_ALGEBRAIC_TTN.md`：实验演进记录。
- `algebraic_ttn/`：精确 TTN、紧凑表示、对称/宇称表示、流式归并和 GPU grouped join。
- `python/`：从基础代数 TTN 到当前对称宇称后端的各阶段命令行入口。
- `src/merge_sorted_runs.cpp`：外部有序归并辅助程序；流式后端会按需编译。
- `tests/`：不依赖逐解枚举或配置 DP 的严格路线测试。
- `data/known_counts.csv`：已知计数，仅供结果核对。
- `tools/build_nqueens_route_pdf.py`：PDF 生成脚本。

## 环境

- Python 3.10 或更新版本
- NumPy
- 使用 GPU 时：与服务器 CUDA 运行时匹配的 CuPy（只安装一种，例如 `cupy-cuda11x` 或 `cupy-cuda12x`）
- 使用磁盘流式有序归并时：支持 C++17 的编译器

CPU 环境示例：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-cpu.txt
```

GPU 环境示例（按集群 CUDA 版本二选一，不要同时安装）：

```bash
python -m pip install numpy cupy-cuda11x
# 或
python -m pip install numpy cupy-cuda12x
```

## 运行

先做一个小规模 CPU 校验：

```bash
python python/contract_symmetric_parity_ttn.py \
  --n-min 1 --n-max 8 \
  --row-reflection-blocks \
  --summary output/cpu_summary.csv
```

8 卡示例；`CUDA_VISIBLE_DEVICES` 中暴露的设备会在程序内重新编号为 `0..7`：

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
python python/contract_symmetric_parity_ttn.py \
  --n-min 12 --n-max 12 \
  --block-reducer cuda \
  --cuda-devices 0,1,2,3,4,5,6,7 \
  --cuda-min-records 1000000 \
  --join-chunk-pairs 4000000 \
  --streaming-merge-strategy sorted-runs \
  --streaming-temp-directory /高速临时盘/nqueens_ttn \
  --row-reflection-blocks \
  --output-directory output/n12 \
  --summary output/n12_summary.csv
```

请先阅读 `docs/GPU_CLUSTER_ROUTE.md` 再调整块大小、临时盘位置和设备列表。V100 与 A100 的显存、CUDA/CuPy 组合和最佳块大小不同，应在目标服务器上实测。

## 测试

从包根目录运行：

```bash
python -m unittest \
  tests.test_algebraic_ttn \
  tests.test_block_reduction \
  tests.test_compact_ttn \
  tests.test_packed_ttn \
  tests.test_parity_ttn \
  tests.test_symmetric_ttn \
  tests.test_symmetric_parity_ttn
```

这些测试覆盖代数张量语义、紧凑/打包表示等价性、分块与流式精确归并、反射对称和宇称扇区。CUDA 不可用时，CPU 测试仍可运行；GPU 路径应在实际 V100/A100 节点上补做设备测试。

## 适用边界

程序已经具备面向多卡的精确分块接口，但这不等于任意较大 `N` 都已在任意机器上可行。`N=15` 的最终资源需求仍取决于中间张量宽度、块大小、磁盘吞吐量和 GPU 内存；运行时若设置 `--max-join-pairs`，触发上限表示预算保护，而不是已经得到最终计数。

