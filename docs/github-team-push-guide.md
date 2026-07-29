# 给组员的 GitHub 分支提交指南

目标：把自己写的代码提交到团队 PR（例如 PR #207）所在的 fork 分支
`EricLi-0321/quantum.harness` 的 `challenge/mps-dissipative-floquet`。
这篇笔记从概念讲起，到生成 token、实际操作，最后是踩坑记录。

---

## 1. 基本概念

### 1.1 仓库、fork、分支

- **上游仓库（upstream）**：主办方的主仓库 `QuantumBFS/quantum.harness`。
  我们都没有对它的写权限，只能读。
- **fork**：组里某个人把上游仓库复制到自己账号下，形成
  `EricLi-0321/quantum.harness`。fork 的所有者可以给其他人开协作权限。
- **分支（branch）**：同一个仓库里的并行开发线。团队 PR 用的是
  `challenge/mps-dissipative-floquet` 这条分支。
- **commit**：一次改动记录，带说明。git 的历史就是一串 commit。
- **push**：把本地 commit 上传到 GitHub 的某个分支。
- **PR（Pull Request）**：把 fork 的某个分支合并进上游仓库的请求。
  **PR 不是静止的**：向它的源分支（这里是
  `EricLi-0321:challenge/mps-dissipative-floquet`）push 新 commit，
  PR 的 commits 列表和 diff 会自动更新。

我们要做的事一句话概括：**在 fork 的分支上追加自己的 commit，然后 push，
PR 就自动包含它了。**

### 1.2 合并的方式

不需要手动合并。只要你的 commit 是接在分支已有历史之后的
（即你在 `git log` 里能看到前面别人的 commit），直接 push 就行。
git 不允许覆盖别人的 commit（除非你加 `-f` 强制，见避坑指南第 8 条）。

---

## 2. 前置条件

1. **让 fork 所有者把你加为 collaborator**（协作者）。由 EricLi-0321 在
   fork 仓库页面操作：`Settings → Collaborators → Add people`，输入你的
   GitHub 用户名。你会收到邀请邮件，**必须点进去接受**。
2. 确认权限：`gh api repos/EricLi-0321/quantum.harness --jq '.permissions'`
   输出里 `"push": true` 就说明你有推送权限。

---

## 3. 生成 GitHub Token

GitHub 不允许用账号密码推送代码，要用 **Personal Access Token（PAT）** 代替密码。

1. 打开 https://github.com/settings/tokens/new
2. **Token name**：随意，如 `harness-push`
3. **Expiration**：选 7 或 30 天（到期后要重新生成）
4. **Scopes** 勾选两项：
   - `repo`（读写仓库内容，push 必需）
   - `read:org`（gh CLI 会检查，缺了会报
     `error validating token: missing required scope 'read:org'`）
5. 点 **Generate token**，复制出来的字符串形如 `ghp_xxxxxxxx...`
   （以 `ghp_` 开头的是 classic token，见避坑指南第 1 条）。

---

## 4. 具体操作

### 4.1 登录 gh CLI（只需做一次，token 过期后重做）

```bash
# 把 token 写进一个临时文件（把 ghp_xxx 换成你刚复制的 token）
echo 'ghp_xxxxxxxxxxxxxxxxxxxx' > /tmp/.gh_token

# 用 token 登录 gh
gh auth login --with-token < /tmp/.gh_token

# 立即删除 token 文件
rm -f /tmp/.gh_token
```

验证：

```bash
gh auth status
```

应看到 `Token scopes: 'read:org', 'repo'`。

### 4.2 克隆 fork 并切到团队分支

```bash
git clone https://github.com/EricLi-0321/quantum.harness.git
cd quantum.harness
git checkout challenge/mps-dissipative-floquet
```

### 4.3 改代码、提交、推送

```bash
# 1. 修改/新增你的文件，比如放到 tracks/mps/solutions/ 下

# 2. 看一下改了什么（好习惯：push 前必看）
git status

# 3. 提交
git add -A
git commit -m "简短说明这次改了什么"

# 4. 确认你在正确的分支、提交内容正确
git log --oneline -3

# 5. 推送（第一次或没有设 tracking 时用完整写法）
git push origin challenge/mps-dissipative-floquet
```

push 成功后，打开 PR 页面刷新，commits 列表里就有你的 commit 了。

### 4.4 别人先推了新 commit 怎么办

push 被拒（non-fast-forward）时说明分支上有了别人的新提交：

```bash
git pull --rebase origin challenge/mps-dissipative-floquet
git push origin challenge/mps-dissipative-floquet
```

`--rebase` 把你的 commit 移到别人 commit 之后，历史保持一条直线。
若 rebase 时有冲突，按终端提示改文件、`git add`、`git rebase --continue`。

---

## 5. 避坑指南

按实际踩坑的惨痛程度排序：

1. **fine-grained token 不能直接用。** 以 `github_pat_` 开头的是
   fine-grained token，默认没有对某个具体仓库的写权限，push 会 403。
   用 `ghp_` 开头的 classic token + `repo` scope 最省心。

2. **`403 Permission denied` 不等于你没权限。** 先查账号权限
   （第 2 节的 `gh api` 命令），账号有 `push: true` 但 token 没写权限
   是最常见原因 —— 换 classic token。

3. **缺 `read:org` scope 会登录失败。** 错误信息是
   `error validating token: missing required scope 'read:org'`。
   重新生成 token 时把 `read:org` 一起勾上。

4. **永远不要把 token 贴到聊天、截图、邮件、代码、commit message 里。**
   token = 你的账号密码。一旦泄露（哪怕贴错窗口），立刻去
   https://github.com/settings/tokens 删掉它（Delete），再生成新的。
   token 用完的临时文件要 `rm` 掉。

5. **不要在装满未跟踪文件的旧目录里 checkout 别的分支。** 如果目录里
   有很多 `git status` 显示 `??` 的文件，而目标分支里同名文件是已跟踪的，
   checkout 会被拒绝（"untracked working tree files would be
   overwritten"）。正确做法：换一个干净目录重新 clone（第 4.2 节），
   或用 `git worktree add 新目录 分支名` 在旁边开一个干净的工作树。

6. **`/tmp` 会被系统清理。** 不要把代码放在 `/tmp` 下指望它明天还在。

7. **push 前必看 `git status` 和 `git log --oneline -3`。** 确认
   (a) 在正确的分支上；(b) commit 里只有你要提交的文件。不要把编译产物、
   数据集、结果目录一股脑 `git add -A` 进去。

8. **不要用 `git push -f`（强制推送）。** 它会覆盖分支上别人的 commit，
   不可恢复。除非全组同意且知道自己在干什么，否则永远不要。

9. **不要把一个从零 `git init` 的仓库直接 push 到团队分支。** 本地
   从零 init 的仓库和团队分支没有共同历史，强行 push 会把整棵树当成
   一个根 commit 覆盖上去。正确做法：先 clone 团队仓库，再在里面加文件。

10. **PR 更新是自动的，不需要重新开 PR。** push 到 fork 的对应分支后，
    原 PR 页面刷新即可看到新 commit 和新 diff。

---

## 6. 一分钟速查

```bash
# 登录（token 过期时重做）
echo 'ghp_xxx' > /tmp/.gh_token && gh auth login --with-token < /tmp/.gh_token && rm /tmp/.gh_token

# 克隆 + 切分支（只需一次）
git clone https://github.com/EricLi-0321/quantum.harness.git
cd quantum.harness && git checkout challenge/mps-dissipative-floquet

# 日常提交
git status
git add -A
git commit -m "说明"
git push origin challenge/mps-dissipative-floquet

# 别人先推了，被拒时
git pull --rebase origin challenge/mps-dissipative-floquet
git push origin challenge/mps-dissipative-floquet
```
