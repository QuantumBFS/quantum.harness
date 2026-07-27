# 文档导航

## 第一次接触这个挑战

读 [ONBOARDING.zh-CN.md](ONBOARDING.zh-CN.md)。它从行列式权重和符号问题讲起，
不要求量子蒙卡或群论基础；读完应当能解释题目在找什么、什么算证据、明天如何参与。

## 开始研究或写代码

查 [FOUNDATIONS.md](FOUNDATIONS.md)。它记录：

- split-orthogonal、Majorana/Kramers 和收缩半群等已知充分条件；
- `O(p,q)`、`Sp(2n,R)`、`SU(p,q)` 等候选的初步淘汰结果；
- 可交给自动测试的精确正、负、零证书；
- 新候选必须通过的新颖性检查；
- 数值 oracle 的正确性和可复现性要求。

## 明天组队时

先读 [../START_HERE.md](../START_HERE.md) 的“现在做到哪里”，再按三类任务分工：

1. 数值 oracle 与测试；
2. 候选矩阵类和物理 DQMC 映射；
3. 文献排重与精确证明。

研究结论只维护在上述两份正文中，避免出现多个互相矛盾的版本。
