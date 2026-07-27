# 从这里开始

## 一句话目标

寻找新的、可映射回具体量子模型的矩阵结构，使辅助场量子蒙卡的每个构型权重
`det(I + exp(A_1) ... exp(A_L))` 始终非负；或者用精确反例排除一个看似可行的候选。

## 现在做到哪里

- 已完成题目拆解、主要已知定理和新颖性边界的调研。
- 已得到 `O(1,1)` 正/负/零控制，以及 `Sp(2,R)`、`SU(1,1)` 的精确负权反例。
- 下一项工程工作是实现数值 oracle：稳定计算权重、生成结构化矩阵并保存可复核运行记录。
- 当前没有正式数值扫描结果，不把“随机扫描没找到负数”误写成数学结论。

## 阅读顺序

1. [中文零基础导读](docs/ONBOARDING.zh-CN.md)：先理解问题、术语和我们为什么这样做。
2. [研究地基](docs/FOUNDATIONS.md)：需要公式、文献、精确证书或候选方向时再查。
3. [文档索引](docs/README.md)：按“入门、研究、明日协作”选择阅读路线。

不需要阅读 `quantum.harness` 的其他 track、skill 或主办方开发文件。

## 工作区边界

```text
signfree-qmc/                 你平时看到的干净入口
├── START_HERE.md             当前状态、阅读顺序、下一步
├── README.md                 队伍和挑战登记
└── docs/                     我们的知识地基
    ├── README.md
    ├── ONBOARDING.zh-CN.md
    └── FOUNDATIONS.md
```

实现开始后会增加：

```text
oracle/                       数值 oracle 源码
tests/                        精确证书和数值回归测试
scripts/                      可重复运行的入口
```

大体积扫描输出遵守比赛仓库约定，写入
`tracks/qmc/results/no-negative-vibes/`，不会混进源码，也不会提交进 Git。

## 唯一日常入口

```bash
cd /home/volper/harness_quantum/signfree-qmc
```

`signfree-qmc` 是一个指向比赛规定 solution 目录的本地入口，因此没有两份文件，也不需要手工同步。

## 下一步

按已经收敛的模块化方案，用测试驱动方式实现 oracle，先让精确正、负、零证书成为自动测试，
再运行小规模确定性基线扫描。
