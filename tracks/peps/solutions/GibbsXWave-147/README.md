# 成员：高建鑫、吴国良、许传书

# 挑战：二维有限温张量网络（#147）

## 模型

研究开放边界 \(10\times10\) 方格上的横场 Ising 模型：

\[
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,\qquad J=1.
\]

重点考察量子临界点 \(h_c/J\approx3.044\) 附近的三个横场：

\[
h/J\in\{2.5,\,3.0,\,3.5\}.
\]

## 目标

将 PEPO 或 METTS 推广到二维系统，计算量子临界扇区
\(\beta J\in[0.1,1.0]\) 内的有限温热力学量：

- 自由能密度 \(f=-\ln Z/(\beta N)\)；
- 内能密度 \(u=\langle H\rangle/N\)；
- 比热
  \(C=\beta^2(\langle H^2\rangle-\langle H\rangle^2)/N\)。

## 当前仓库内容

本目录汇总了三条互相补充的计算与验证路线：

| 目录 | 主要内容 | 当前作用 |
|---|---|---|
| [`2DMETTS/`](2DMETTS/) | 有限 PEPS、simple update、boundary-MPS 收缩和二维 METTS；包含算法说明、Julia 代码以及现有尺寸与参数下的结果 | 二维有限温主算法与阶段性数值结果 |
| [`Born_sampling_mps/`](Born_sampling_mps/) | MPS Born sampling 的方法说明、绘图数据与 \(10\times10,\ h/J=3\) 的 SSE 对比图 | 提供另一条有限温随机采样路线及临界场附近的交叉检查 |
| [`sse-qmc-validation-package/`](sse-qmc-validation-package/) | SSE-QMC 实现快照、Sandvik 更新示意、绘图脚本、数据、TeX/PDF 说明及 \(2\times2\)、\(4\times4\) 对照 | 解释并验证作为基准方法的 SSE-QMC |

三个目录均保留代码、说明文档、数据和现有图表，便于分别阅读和复现。
其中结果是当前阶段的工作与验证快照，尚不能替代挑战要求的全部
\(10\times10\)、三个横场、完整温区和自由能结果。

## 挑战交付要求

| 序号 | 交付内容 | 类别 |
|---|---|---|
| 1 | 在 \(\beta J\in[0.1,1.0]\) 上给出 \(f(T)\)、\(u(T)\)、\(C(T)\) 曲线 | 必做 |
| 2 | 给出关于键维数 \(D\) 或样本数的收敛分析与图像 | 必做 |
| 3 | 使用 QMC 参考数据验证结果 | 必做 |
| 4 | 提供源代码、技术文档和一条命令即可运行的测试脚本 | 必做 |
| 5 | 与 tanTRG 比较精度、时间和内存 | 加分 |
| 6 | 计算均匀磁化率 \(\chi(T)\) | 加分 |

## 验证标准

- **QMC 对照：** 在相同 \(10\times10\) 开放边界格点上，与
  SSE 或 worm QMC 比较全部目标热力学量。
- **收敛性：** PEPO 路线检查
  \(D\in\{4,6,8\}\) 下的 \(u\) 和 \(C\)；METTS 路线检查样本数收敛，
  并在 \(\beta J=0.8\) 处达到 \(u\) 相对误差小于 \(1\%\)、
  \(C\) 相对误差小于 \(3\%\)。
- **可复现性：** 使用开放源代码（Julia/TensorKit），并提供一条命令即可运行的测试脚本。

## 阅读入口

1. 项目阶段性总结：
   [`2d_finite_temperature_tensor_networks.pdf`](2d_finite_temperature_tensor_networks.pdf)；
2. 二维 METTS 的整体说明：[`2DMETTS/2DMETTS.md`](2DMETTS/2DMETTS.md)；
3. Born sampling 说明：[`Born_sampling_mps/README.md`](Born_sampling_mps/README.md)；
4. SSE-QMC 验证包说明：
   [`sse-qmc-validation-package/README.md`](sse-qmc-validation-package/README.md)。
