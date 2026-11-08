---
name: theorem-formalize
description: 书里要写一条 trureturing 中尚未冻结的定理时使用：先在 trureturing 仓库完成 Lean 形式化、Blueprint 与冻结，再回到书仓库钉版引用。本仓库不写 Lean。
---

# 让一条定理可以进书

## 适用范围

**用**：某条定理、引理、命题或推论在 trureturing 中找不到已冻结的 Lean 声明；或者已有声明的陈述与书中想写的不一致。

**不用**：声明已冻结、只是书中还没引用（直接写，见 `skills/book-write`）；升级所钉的提交（`skills/trureturing-pin`）。

**权威**：Lean 形式化的全部规则在 trureturing 仓库：它的 `CLAUDE.md`、`docs/develop/spec/golden-ledger-repo-spec.md` 与 `skills/codex-formalize/SKILL.md`。本文件只描述书仓库与 trureturing 之间的往返。冻结成员身份的唯一判据是 `Golden/Frozen/state/<module>.lean.json` 存在且列有该声明。

## 先读

- 本仓库：`docs/VERIFICATION.md`、`trureturing.lock.json`、`site.toml` 的 `[trureturing]`。
- trureturing：`CLAUDE.md`（尤其冻结律、检索顺序、文档是投影）、`skills/codex-formalize/SKILL.md`、`agents/CONTEXT.md`。

## 步骤

### 0. 先找，再写

1. 在 trureturing checkout（`$TRURETURING_DIR` 或 `../trureturing`；没有就 `git clone https://github.com/the-omega-institute/trureturing ../trureturing`）中检索：`D5/` 的声明 → 钉版 mathlib → 其他。按 trureturing 的检索顺序找可复用的已冻结声明。
2. 找到 → 记下 GID（`<模块路径>.<声明名>`），确认 `Golden/Frozen/state/<模块路径>.lean.json` 里有它且 `kind` 为 `theorem`，回到本仓库写作即可。
3. 找到但陈述不同 → 判断书中陈述能否作为它的忠实特例或推论；能，就在 trureturing 里补一条小定理（仍走下面的流程），不要在书里“近似地”引用。

### 1. 在 trureturing 中形式化

在 trureturing 仓库按它的 `skills/codex-formalize/SKILL.md` 工作：写 D5 Lean 与 Blueprint Scribe，`lake build`、无 `sorry`、只用标准公理，经它的 CI 与评审合入 `dev`，并完成冻结（状态片写入 `Golden/Frozen/state/`）。

- 在 PR 说明里写明这条定理将被哪本书的哪一章引用。
- 不要为了书的措辞去扭曲形式陈述；书跟随 Lean，不是反过来。

### 2. 回到书仓库

1. `./tbook pin` —— 跟随 `site.toml` 中的分支（默认 `dev`）移到含新冻结状态片的提交；或 `./tbook pin <sha>` 钉到确切提交（完整或缩写 SHA）。该提交必须已在 `dev` 上：PR 尚未合入时，其 head 提交会被拒绝（trureturing 只在 `dev` 上执行冻结律）。
2. 阅读 pin 报告：除了新增的 GID，若有“module statement digest changed”，按 `skills/trureturing-pin` 复核受影响的定理文字。
3. 在章节中写 `::: {.theorem #thm-… lean="<GID>"}`，所有语言版本同步。
4. `./tbook check` 0 错误；提交时把 trureturing 的 PR 链接写进提交说明。

### 3. 定期深度验证

`./tbook check` 读取冻结状态片（快、每个 PR 都跑）。发版前或每周由 `.github/workflows/lean-verify.yml` 生成 Lake 工程，对每条被引用的声明重新检查存在性、所在模块、种类与公理闭包（仅 `propext`、`Classical.choice`、`Quot.sound`）。本地可运行 `./tbook lean-project` 后按生成的 `README.md` 执行。

## 禁止

- 在本仓库写 `.lean` 文件，或把 Lean 片段当作“证明”贴进书里。
- 引用未冻结的声明、私有声明，或 `D5/*_Frontier/` 中的开放边界。
- 手改 `trureturing.lock.json`。
- 在 trureturing 合入前就把结论写成定理；在此之前它只能是 `conjecture`。
