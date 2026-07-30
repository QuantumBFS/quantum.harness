# Challenge 148

本目录研究三角晶格与蜂窝晶格横场 Ising 模型临界场之比是否严格等于
\(\sqrt 5\)。

- 中文阶段报告：[挑战148汇报](挑战148汇报.md)
- 物理与软件设计：[DESIGN](DESIGN.md)
- 实现计划：[PLAN](PLAN.md)
- 报告配图与机器可读点估计：[`report-assets/`](report-assets/)

当前状态：代码管线和 72+24 个 QMC_SSE 方法学 pilot 已完成，共形成 96 个
可验证 cell、1536 个 immutable bin 和 153600 个保留样本；140-cell 论文
几何扫描及修正后的 ED–Rust–Julia acceptance 已完成实现与测试，列为下一阶段
生产任务。正式数据完成后即可在现有管线上输出临界场比值判决。

报告配图依赖 Git 未跟踪的完整 `runtime/coarse-crossing-v1e` 和
`runtime/directed-extension-v2` 证据树。正式提交前仍需把它们发布为带
SHA-256 的可下载归档，并在报告中补充下载位置。
