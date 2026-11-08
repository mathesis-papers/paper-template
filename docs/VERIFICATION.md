# 验证模型 · Verification model

本书库承诺：**书中每一条定理、引理、命题与推论，都对应 trureturing 中一条已被 Lean 内核验证并冻结的声明，且固定在一个确切的提交上。** 本文说明这条承诺如何被检查、检查到什么程度，以及什么仍需人工负责。

## 1. 一条定理的身份链

```
书中环境  ::: {.theorem #thm-x lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
   │  GID = <模块路径>.<声明名>
   ▼
trureturing.lock.json   commit = 8a24ea4e…（40 位 SHA）
   │  name = D5.S1.Deficit.deficit_three_valued, kind = theorem,
   │  statement_id = sha256:…（模块陈述摘要）, line = 264
   ▼
trureturing @ commit:  Golden/Frozen/state/D5/S1/Deficit/DeficitThreeValued.lean.json
   │  {statement_id, declarations: [{declaration_name_key: "ns(…,20:deficit_three_valued)", kind: "theorem"}]}
   ▼
trureturing @ commit:  D5/S1/Deficit/DeficitThreeValued.lean   （Lean 源；由 trureturing 的 CI 以 lake build 与公理检查保证）
```

trureturing 的冻结律（其 `CLAUDE.md` §1.3）规定：**模块的状态片 `Golden/Frozen/state/<module>.lean.json` 存在，当且仅当该模块已冻结**；状态片只在声明经内核验证（无 `sorry`、无私有公理）后由 trureturing 的流程写入。因此“在所钉提交上，状态片列有该声明且种类为 theorem”就是本书库对“已经 Lean 验证”的判据。

这条判据只在 trureturing 的集成分支上成立：冻结律由 trureturing 的 CI 在 `site.toml` 的 `[trureturing].branch`（默认 `dev`）上执行。GitHub 也会按 SHA 提供从未合入的提交（任何人发起的 PR 的 head、其他分支），那些提交上的状态片可以是任意内容。所以**所钉提交必须能从该分支到达**：`./tbook pin` 拒绝不在分支上的提交，`./tbook check` 每次复核（§2）。锁文件的 `branch` 字段记录的就是被核对的分支。

## 2. 每个 PR 都运行的检查（`./tbook check`）

| 检查 | 失败时 |
| --- | --- |
| 形式结论必须有 `lean`；开放条目不得有 `lean` | 错误 |
| 所钉提交可从 `site.toml` 的 trureturing 分支到达 | 错误；无法判定时：GitHub Actions 中为错误，本地或 `--offline` 下为警告 |
| GID 语法（与 trureturing Blueprint 相同的地址格式；声明名是 Lean 名，分量可含希腊字母等类字母符号、下标与 `'` `!` `?`，其他分量写成 `«…»`；不得含空白或逗号） | 错误 |
| 每个被引用的 GID 都在锁文件中 | 错误，提示 `./tbook pin --refresh` |
| 形式结论引用的声明种类为 `theorem` | 错误 |
| 在锁定提交上重新读取状态片：名称、种类、模块、`statement_id` 与锁文件一致 | 错误（锁文件过期或被手改） |
| 声明解析：在模块状态片中按完整名或名称分量后缀恰好匹配一个非私有声明 | 错误（不存在 / 有歧义 / 模块未冻结） |
| 多语言版本的环境序列（种类、id、Lean 引用）逐条一致；SUMMARY 结构（前言/编号/附录章节、嵌套、草稿条目）一致，使同一定理在各语言中编号相同 | 错误 |
| 锁文件中有未被任何书引用的条目（`--book` 时也计入其他书的引用） | 警告 |
| `.cache/` 下有提交入库的文件（缓存只在本地可信） | 错误 |

状态片的来源依次为：本地 trureturing checkout（`$TRURETURING_DIR` 或 `../trureturing`，用 `git show <commit>:<path>`）、缓存 `.cache/trureturing/<commit>/`、`raw.githubusercontent.com/<repo>/<commit>/<path>`。因为路径中带着完整 SHA，读到的内容不可变。

分支可达性的判定依次为：缓存 `.cache/trureturing/<commit>/.tbook-on-branch.json` 中的肯定结果；本地 checkout 的 `git merge-base --is-ancestor <commit> <ref>`，`<ref>` 依次取指向该仓库的远程的跟踪分支、`origin/<branch>`、本地 `<branch>`；联网时 GitHub compare API `repos/<repo>/compare/<branch>...<commit>`（状态为 `behind` 或 `identical` 才算在分支上）。GitHub 的回答优先于可能过期的 checkout；只有肯定结果会被缓存。访问 API 时依次使用 `$TRURETURING_TOKEN`、`$GITHUB_TOKEN`、`$GH_TOKEN`（未设置时匿名，每小时 60 次）。

## 3. 深度验证（`lean-verify` 工作流）

状态片是 trureturing 自己的账本。为了不只依赖账本，`./tbook lean-project` 生成一个 Lake 工程：

- `lean-toolchain` 取自所钉提交；`lakefile.toml` 以 `rev = <commit>` 依赖 trureturing；
- 导入每个被引用的模块，对每条声明检查：存在；位于预期模块；种类与锁文件一致；`collectAxioms` 的结果只含 `propext`、`Classical.choice`、`Quot.sound`（因而没有 `sorryAx`）。

它需要构建被引用模块及其依赖（Mathlib 用 `lake exe cache get`），耗时较长，所以每周和发版前运行（`.github/workflows/lean-verify.yml`；设置仓库变量 `REQUIRE_LEAN_VERIFY=true` 可让 Release 依赖它）。

## 4. 升级所钉提交时

`./tbook pin` 先核对目标提交在 `site.toml` 的分支上（不在则 **Refused**，锁文件不写；无法判定时 GitHub Actions 中拒绝、其他情况列为 **Warnings**），再列出：新增与删除的 GID（仍被引用但无法解析的只列在 Unresolved）、名称或种类变化、**模块陈述摘要变化**、源码行号变化。`statement_id` 是模块级摘要：它变了，说明该模块中至少一条声明的陈述变了，不一定是你引用的那条。合并前必须对照新旧提交的 Lean 源复核被引用定理的陈述，并同步书中文字（`skills/trureturing-pin`）。

## 5. 不由机器保证、需要人工负责的部分

- **书面陈述与 Lean 陈述一致。** 工具能保证“引用的声明存在且已验证”，不能保证“书中的话说的就是那条声明”。写作与评审时必须对照 Lean 源（链接带行号）和 trureturing 的 Blueprint 说明。
- **解释与图示。** `proof` 块、正文、可视化与视频只是解释或示意，不承担证明；可视化页面必须声明哪些是示意模型。
- **trureturing 自身的正确性**由它的 CI、Lean 内核与评审流程负责；本书库信任其冻结账本，并通过深度验证独立复核公理闭包。

## 6. 读者如何自行核对

每个定理框的 `LEAN ✓` 徽章与页脚链接指向所钉提交上的 Lean 源文件（含行号；行号按 `namespace`/`section` 解析出的完整名定位，无法唯一确定时不带行号，而不是猜一个）；书末“形式化验证账本”列出全部对应关系与状态片链接。读者可以克隆 trureturing，检出该提交，运行 `lake build` 并对声明执行 `#print axioms`。
