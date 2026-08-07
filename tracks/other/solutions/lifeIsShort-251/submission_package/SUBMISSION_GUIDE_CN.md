# 投稿操作指南

## 推荐路线

本稿当前最合适的首投目标是 **The Electronic Journal of Combinatorics (E-JC)**。论文的核心属于图论、组合概率与稳定多项式，主题与该刊范围吻合；初稿允许保留完整证明和审计附录。

建议顺序：

1. 由署名作者本人完成最终核验并明确同意公开与投稿；
2. 请一位熟悉 real stable polynomials / negative dependence 的研究者做独立逐行审读；
3. 上传 arXiv（主分类 `math.CO`，可交叉分类 `math.PR`）；
4. 向 E-JC 提交初稿 PDF；
5. 同一时间只接受一家期刊审理。

E-JC 的当前 checklist 禁止已经正式发表或同时由另一家期刊审理的稿件。arXiv 是预印本平台而不是另一家期刊，但提交当天仍应由作者重新阅读该刊最新政策。

## 0. 投稿前不可省略的人工步骤

- **Shigang Ou 本人**明确同意署名、arXiv 公开和期刊投稿，并接受完整学术责任。
- 本人逐行检查证明、引用、作者单位和 AI 辅助披露。
- 填写本人真实有效的电子邮箱；本包没有猜测或生成邮箱。
- 核验两项关键 imported results 的使用版本：Borcea--Brändén algebraic-symbol criterion；Borcea--Brändén--Liggett 的 strongly Rayleigh implication。
- 用 MathSciNet 或 zbMATH 再做一次关键词和引用追踪，特别检索：
  `incident-edge marginal`, `vertex-star marginal`, `cocircuit marginal`,
  `rooted forest polynomial`, `component-marked forest polynomial`,
  `stability preserver`, `unrooting operator`。
- 打开 `REQUIRED_AUTHOR_ACTIONS.md` 并逐项完成。

## 1. arXiv 投递

### 使用文件

上传 `arxiv_source.zip`。压缩包根目录含 `main.tex`；`anc/` 中是审计脚本和确定性回归日志。不要只上传由 TeX 生成的本地 PDF 来代替源码。

### 表单建议

- Title：见 `submission_metadata.md`
- Authors：Shigang Ou
- Primary category：`math.CO`
- Cross-list：`math.PR`
- Comments：复制 `submission_metadata.md` 中的 arXiv comments
- Abstract：复制 plain-text abstract
- License：由作者根据单位或资助方要求自行选择

### 上传后检查

- 确认自动识别的 top-level file 是 `main.tex`。
- 查看 arXiv 自动生成的 PDF 预览，逐页核对公式、作者、单位和参考文献。
- 确认 source 中没有草稿注释、隐私信息或不应公开的文件。
- 若账户需要 endorsement，按 arXiv 页面提示完成。
- 最终提交必须由作者本人完成；不要以他人身份代投。

## 2. E-JC 投递

### 使用文件

最方便的是解压 `EJC_initial_submission_materials.zip`。初次投稿时，正文栏只上传：

- `Stable_Incident_Edge_Marginals.pdf`

E-JC 当前指南要求初稿正文为 PDF，并明确说初审阶段不要上传 LaTeX 源码。正文附录已经自足；除非系统有明确且合适的 supplementary 栏，否则审计脚本可以先不交。

### 表单内容

- Article type：Research article
- Title / author / affiliations：见 `submission_metadata.md`
- Email：作者本人真实邮箱
- Abstract：使用 `submission_metadata.md` 中的 HTML abstract；不要使用自定义 LaTeX 宏
- Keywords：复制 metadata 文件中的关键词
- Cover letter：使用 `EJC_cover_letter.txt`，或在系统允许时上传 `EJC_cover_letter.pdf`

### 必须确认的声明

- 稿件未正式发表，且未同时被另一家期刊审理；
- 所有署名作者同意以当前形式投稿；
- 论文为原创、自足，并正确标注所有 imported results；
- 已阅读并遵守 E-JC 的 AI policy；
- 接收后愿意使用 E-JC 的 `e-jc.sty` 重新排版。

### 系统操作

1. 作者注册或登录 E-JC 投稿系统；
2. 按系统的五步流程建立 submission；
3. 输入作者姓名、单位和邮箱；
4. 粘贴 HTML abstract；
5. 上传 `Stable_Incident_Edge_Marginals.pdf`；
6. 在 Comments for the Editor 中说明审计附录为正文的一部分，有限回归仅为 diagnostic；
7. 提交前下载或预览系统记录，再核对一次元数据。

## 3. 期刊选择判断

- **首投：E-JC。** 这是当前稿件的合理匹配，而不是“必收”。
- 若 E-JC 因范围或贡献规模拒稿，应先按意见修订，再考虑更稳妥的综合组合期刊，例如 *Australasian Journal of Combinatorics*。
- *Combinatorics, Probability and Computing* 的主题也匹配，但门槛通常更高；更适合作为在定理进一步推广之后的进取选择，而不是机械的拒稿后备份。
- 不要向两家期刊同时投稿。

## 4. 审稿人最可能追问的问题

- differential-unrooting 的系数消去为何对标记平行边仍成立？
- 算子 `1 - lambda partial_i partial_j` 的 algebraic symbol 符号是否正确？
- “外部条件化”是否严格只指 coordinate conditioning？
- Poisson-binomial 推论在参数为 0 或 1 时如何处理？
- 是否已有 matroid cocircuit / graph star marginal 的同构先例？
- 为什么局部 star stability 不推出不相邻边的负相关？

稿件正文和附录已经直接回答前四项；第五项仍需要作者和领域专家完成最终先例审计。

## 5. 文件对应关系

- `Stable_Incident_Edge_Marginals.pdf`：可读稿 / E-JC 初稿正文
- `incident_edge_marginals.tex`：自足 LaTeX 源码
- `arxiv_source.zip`：arXiv 上传包
- `EJC_initial_submission_materials.zip`：E-JC 初投材料
- `manuscript_source_and_audit.zip`：源码与审计脚本
- `full_submission_bundle.tar.gz`：完整归档包
- `archival_low_cyclomatic_certificates.zip`：早期低圈秩探索，**不属于当前投稿正文**
- `SHA256SUMS`：校验和
