---
name: trureturing-pin
description: 升级或刷新本书库所钉的 trureturing 提交时使用（./tbook pin），包括处理自动 bump PR：解析全部 Lean 引用、复核陈述摘要发生变化的定理文字、确保 ./tbook check 通过。
---

# 升级所钉的 trureturing 提交

## 适用范围

**用**：想引用 trureturing 新冻结的声明；`trureturing-bump` 工作流开了 PR；`./tbook check` 报告锁文件与上游不一致；新增引用后锁文件缺条目。

**权威**：`tools/tbook/pin.py` 的行为与 `./tbook check` 的输出。

## 三种用法

```bash
./tbook pin              # 跟随 site.toml [trureturing].branch（默认 dev）到最新提交
./tbook pin <sha|ref>    # 钉到指定提交（完整或缩写 SHA）、分支或 tag
./tbook pin --refresh    # 不动提交；解析新增引用、清理不再使用的条目
```

加 `--dry-run` 只看报告不写锁文件；加 `--report build/pin.md` 把报告写成文件（PR 正文用，目录不存在时自动创建）。

无论哪种写法，目标提交都必须能从 `site.toml` 的分支（默认 `dev`）到达：trureturing 只在该分支上执行冻结律，GitHub 却也按 SHA 提供未合入的提交（PR head、其他分支）。不在分支上的提交会被拒绝（报告中的 **Refused**，锁文件不写）；无法判定时（没有含该提交的本地 checkout，且 GitHub API 不可用或加了 `--offline`），在 GitHub Actions 中（未加 `--offline`）拒绝，其他情况写入锁文件并在 **Warnings** 中提示，之后由 `./tbook check` 再次核对。本地 checkout 的 `origin/dev` 过期时先 `git -C ../trureturing fetch`。只支持分支（`refs/heads/*`）与 tag（`refs/tags/*`），不支持 `refs/pull/*`。

## 步骤

1. 运行 `./tbook pin --dry-run`，读报告：
   - **Refused**：目标提交不在所跟随的分支上（或在 CI 中无法核对）。改钉已合入该分支的提交；不要为此修改 `site.toml` 的分支。
   - **Unresolved**：某个 GID 在新提交上不存在或未冻结（模块被移动、改名、删除冻结状态片）。到 trureturing 查明原因（`git log -- Golden/Frozen/state/<module>.lean.json`），改用新的 GID，或把条目降级为 `conjecture` 并说明。锁文件在全部解析前不会写入。
   - **Changed — module statement digest changed**：该模块中某些声明的陈述变了（`statement_id` 是模块级摘要，不一定是你引用的那条）。逐条打开新旧两个提交上的 Lean 源，比较被引用声明的陈述；若变了，更新所有语言版本中的书面陈述。
   - **name/kind changed**：后缀匹配到了别的声明，或声明种类变化。改用更长的名字后缀。
   - **Source line changed**：只是源码行号变化（链接随之更新），无须改书；若同一 GID 也列在 **Changed** 中，按 Changed 的要求复核。
2. 确认无误后去掉 `--dry-run` 正式运行。
3. `./tbook check` 必须 0 错误。
4. 构建并抽查受影响的章节（`./tbook build html --book <slug>`）。
5. 提交 `trureturing.lock.json` 与书的改动，说明：新旧提交、新增/删除的 GID、复核过的定理。

## 自动 bump PR

`.github/workflows/trureturing-bump.yml` 每周运行 `./tbook pin` 并开 PR，正文是 pin 报告与 `./tbook check` 输出。合并前必须由人或 agent 完成上面第 1 步的复核；有 “statement digest changed” 时，在 PR 中逐条写下复核结论。

## 禁止

- 手改 `trureturing.lock.json`。
- 钉未合入所跟随分支的提交（例如自己尚未合并的形式化 PR 的 head）。
- 提交 `.cache/` 下的文件（`./tbook check` 报错）。
- 为让检查通过而删除 `lean` 属性或把定理改成注释。
- 在未复核陈述变化的情况下合并 bump PR。
