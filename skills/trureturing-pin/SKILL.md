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
./tbook pin <sha|ref>    # 钉到指定提交、分支或 tag
./tbook pin --refresh    # 不动提交；解析新增引用、清理不再使用的条目
```

加 `--dry-run` 只看报告不写锁文件；加 `--report build/pin.md` 把报告写成文件（PR 正文用）。

## 步骤

1. 运行 `./tbook pin --dry-run`，读报告：
   - **Unresolved**：某个 GID 在新提交上不存在或未冻结（模块被移动、改名、删除冻结状态片）。到 trureturing 查明原因（`git log -- Golden/Frozen/state/<module>.lean.json`），改用新的 GID，或把条目降级为 `conjecture` 并说明。锁文件在全部解析前不会写入。
   - **Changed — module statement digest changed**：该模块中某些声明的陈述变了（`statement_id` 是模块级摘要，不一定是你引用的那条）。逐条打开新旧两个提交上的 Lean 源，比较被引用声明的陈述；若变了，更新所有语言版本中的书面陈述。
   - **name/kind changed**：后缀匹配到了别的声明，或声明种类变化。改用更长的名字后缀。
2. 确认无误后去掉 `--dry-run` 正式运行。
3. `./tbook check` 必须 0 错误。
4. 构建并抽查受影响的章节（`./tbook build html --book <slug>`）。
5. 提交 `trureturing.lock.json` 与书的改动，说明：新旧提交、新增/删除的 GID、复核过的定理。

## 自动 bump PR

`.github/workflows/trureturing-bump.yml` 每周运行 `./tbook pin` 并开 PR，正文是 pin 报告与 `./tbook check` 输出。合并前必须由人或 agent 完成上面第 1 步的复核；有 “statement digest changed” 时，在 PR 中逐条写下复核结论。

## 禁止

- 手改 `trureturing.lock.json`。
- 为让检查通过而删除 `lean` 属性或把定理改成注释。
- 在未复核陈述变化的情况下合并 bump PR。
