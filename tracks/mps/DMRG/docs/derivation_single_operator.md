# 单算符变分 RG 的严格推导

依据：accepted manuscript 第 2 页，Eq. (5)-(12)。本推导只使用正文已明确给出的定义，不引入 Supplementary Material 中尚未取得的参数。

## 1. 定义

采用总和型最近邻算符

\[
S(\sigma)=-\sum_{\langle ij\rangle}\sigma_i\sigma_j,
\qquad H(\sigma)=K S(\sigma).
\]

经过粗粒化 `sigma' = tau(sigma)` 后，只保留一个块最近邻算符：

\[
S_b(\sigma')=-\sum_{\langle IJ\rangle}\sigma'_I\sigma'_J,
\qquad V_J(\sigma')=J S_b(\sigma').
\]

带偏置的微观分布为

\[
p_J(\sigma)=\frac{1}{Z_J}
\exp[-K S(\sigma)-J S_b(\tau(\sigma))].
\]

## 2. 变分目标

由论文 Eq. (5)，单参数目标可写为

\[
\Omega(J)=\log\frac{Z_J}{Z_0}
+J\langle S_b\rangle_{p_t}.
\]

论文采用均匀目标分布。对非平凡自旋乘积算符，独立均匀自旋给出

\[
\langle S_b\rangle_{p_t}=0.
\]

所以

\[
\Omega(J)=\log\frac{Z_J}{Z_0}.
\]

注意：`Z_J` 仍由带偏置权重定义，因此不是常数。

## 3. 梯度与 Hessian

对 `J` 求导：

\[
\frac{d\Omega}{dJ}
=-\langle S_b\rangle_J
\equiv g(J).
\]

再求一次导数：

\[
\frac{d^2\Omega}{dJ^2}
=\langle S_b^2\rangle_J-\langle S_b\rangle_J^2
=\operatorname{Var}_J(S_b)\ge 0.
\]

因此 `Omega` 为凸函数。只要 `S_b` 在当前分布下不是常数，方差严格大于 0，极小点唯一。

同时有

\[
\frac{d\langle S_b\rangle_J}{dJ}
=-\operatorname{Var}_J(S_b)\le 0.
\]

这给出一个不依赖优化器的符号检查：增大 `J` 时，`mean(S_b)` 必须单调减小。

## 4. 极小条件与 Newton 更新

极小点满足

\[
g(J_*)=0
\quad\Longleftrightarrow\quad
\langle S_b\rangle_{J_*}=0.
\]

精确 Newton 步为

\[
J_{n+1}
=J_n-\frac{g(J_n)}{\operatorname{Var}_{J_n}(S_b)}
=J_n+\frac{\langle S_b\rangle_{J_n}}
{\operatorname{Var}_{J_n}(S_b)}.
\]

例如无偏临界铁磁构型通常有 `mean(S_b)<0`，第一步必须使 `J` 变负。若程序得到相反方向，说明算符负号、梯度或接受率至少一处错误。

## 5. 与 Metropolis 接受率的一致性

单个微观自旋翻转的有效能量差是

\[
\Delta H_{\mathrm{eff}}
=K\Delta S+J\Delta S_b.
\]

若该翻转未改变所属块的多数自旋，则 `delta S_b=0`。若块自旋 `sigma'_I` 翻转，则

\[
\Delta S_b
=2\sigma'_I\sum_{J\in\mathrm{nn}(I)}\sigma'_J.
\]

接受率为

\[
P_{\mathrm{acc}}=\min(1,e^{-\Delta H_{\mathrm{eff}}}).
\]

这与当前实现的局部增量公式完全一致，并已通过全量重算测试。

## 6. 恒等 RG 的精确可解验收

令粗粒化为恒等映射：

\[
\tau(\sigma)=\sigma,
\qquad S_b=S.
\]

此时带偏置哈密顿量为

\[
H+V=(K+J)S.
\]

均匀目标分布对应有效耦合为 0，因此唯一极小点必须满足

\[
K+J_*=0,
\qquad J_*=-K.
\]

由论文 Eq. (12)：

\[
K'=-J_*=K.
\]

这正是恒等 RG 必须给出的结果。该测试同时验证：

1. `S=-sum sigma_i sigma_j` 的负号；
2. Boltzmann 权重中的 `H+V` 号；
3. 梯度 `g=-mean(S)`；
4. Hessian `Var(S)`；
5. 读出关系 `K'=-J*`。

## 7. 对当前复现的结论

恒等 RG 验收通过后，才能把相同符号体系用于 `3 x 3` 多数粗粒化。`3 x 3` 的单算符结果只是截断投影；只有完整算符基底能够逼近论文的重整化哈密顿量。

当前仍不能从正文推出论文的精确随机优化日程。故不能通过修改学习率、轨迹平滑或挑选收敛区间，把诊断轨迹当作论文级结果。
