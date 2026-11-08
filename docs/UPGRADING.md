# 模板升级 · Upgrading the template

本书库基于 [trureturing-books-template](https://github.com/the-omega-institute/trureturing-books-template)。模板以语义化版本发布（tag `vX.Y.Z`），下游书库通过 `./tbook template update` 升级。

## 1. 托管与自有

`template.toml` 定义了边界：

- **托管**（`[managed].paths`）：`tools/`、`theme/`、`templates/`、`skills/`、`docs/`、`.github/workflows/`、`.github/actions/`、`.claude/`、`CLAUDE.md`、`AGENTS.md`、`tbook`、`template.toml`、`template-manifest.json`、`requirements.txt`、`package.json`、`package-lock.json`、`.gitignore`、`.editorconfig`。升级时同步（新增、修改、删除）。
- **例外**（`[managed].exclude`）：`skills/local-*`（书库自己的 skill）、`docs/project/`（书库自己的文档）。
- **自有**：`books/`、`site.toml`、`trureturing.lock.json`、`i18n/`、`PROJECT.md`、`README.md`、`LICENSE`，以及任何不在托管路径下的文件。升级永不触碰。

`template-manifest.json` 记录当前版本每个托管文件的 sha256 与权限位，用来判断“本地是否改过”。

## 2. 升级

```bash
./tbook template status              # 当前版本；本地改过、缺失、多出的托管文件
./tbook template update --dry-run    # 预览到最新版本的变化
./tbook template update              # 执行；--to vX.Y.Z 指定版本；--source <路径或 git URL> 指定来源
```

不带 `--to` 时目标是最新的正式发布（`vX.Y.Z`，不含预发布；`--source` 是普通目录时，目标就是该目录），而且**从不倒退**：最新发布比 `template.toml` 的版本旧（例如书库用 `--to` 升到了预发布），或版本号相同但托管文件来自另一个快照（例如在两次发布之间从模板 `main` 分支创建的书库），命令什么也不改，只在摘要中说明原因。确需降级或与该发布重新同步时，用 `--to` 明确指定版本。

每个托管文件按三方比较处理（基准是本地清单记录的旧版本）：

| 本地 | 上游 | 结果 |
| --- | --- | --- |
| 未改 | 改了 / 新增 / 删除 | 采用上游 |
| 改了 | 未改 | 保留本地 |
| 改了 | 改了 | **冲突**：保留本地，上游版本写入 `<file>.template-new` |

“本地删除”指书库曾经有过这个文件：清单列出、但本地不存在且 git 历史中从未出现过的文件（例如接入模板时复制来的清单所列的文件，见第 5 节）按“上游新增”安装。浅克隆或不是 git 仓库时无法判断，按清单处理。

有冲突时命令以退出码 3 结束（`--dry-run` 预览时，若真正执行会冲突，同样返回 3）。逐个合并后删除 `.template-new` 文件。`--force` 直接采用上游（会丢弃本地改动，慎用）。`--source` 接受 git URL、本地 git 仓库或普通目录（此时不能用 `--to`）。`--to` 接受版本号、tag、分支或提交 SHA；来源是 URL 时 SHA 须写完整的 40 位，本地 git 仓库也接受缩写。摘要语言默认是 `site.toml` 中 `languages` 的第一个，`TBOOK_LANG=zh|en` 可指定。

升级完成后会运行 `tools/migrations/` 中跨越版本的迁移脚本（取自新版本模板，各在一个新的 Python 进程中运行，见 `tools/migrations/README.md`），并把摘要写到 `build/template-update.md`。然后：

```bash
.venv/bin/pip install -r requirements.txt && npm ci
./tbook doctor && ./tbook check && ./tbook build all
```

## 3. 自动升级 PR

`.github/workflows/template-sync.yml` 每周检查模板的新版本，执行升级并开 PR（分支 `template-update/<version>`）；有冲突时 PR 标题以 `[conflicts]` 开头，`.template-new` 文件一并提交供合并。没有更新的发布时（见第 2 节，不会倒退）什么也不改，不开 PR。模板仓库至少发布过一个版本（tag `vX.Y.Z`）后它才会工作。

令牌：

- 只用 `GITHUB_TOKEN` 时，需在 Settings → Actions → General 勾选 “Allow GitHub Actions to create and approve pull requests”；这样开的 PR 不会自动触发 CI，且升级若改动 `.github/workflows/`，推送会被 GitHub 拒绝（工作流会给出说明后失败）。
- 推荐在仓库 Secrets 中设置 `BOT_TOKEN`：细粒度令牌，Contents、Pull requests 与 **Workflows** 均为读写。

## 4. 改进托管文件

不要在书库中长期修改托管文件：把改进提交到模板仓库（流程见 `skills/template-update/SKILL.md` 的 B 节），发布新版本后再升级回来。

## 5. 不是从模板创建的仓库

已有仓库也可以接入：

1. 从模板的一个发布（通常是最新版 `vX.Y.Z`）复制 `tbook`、`tools/` 与 `template.toml` 到仓库根目录，并提交。不需要复制 `template-manifest.json`：升级会写入它。
2. 运行：

   ```bash
   ./tbook template update --source https://github.com/the-omega-institute/trureturing-books-template.git --to vX.Y.Z
   ```

   `--to` 取第 1 步复制的版本（复制的是最新版时可以省略）。结果：
   - 其余托管文件（`theme/`、`skills/`、`docs/`、`.github/workflows/` 等）全部新增；复制来的文件与该发布相同，保持不变。
   - 仓库已有、内容不同的同名托管文件（例如自己的 `.gitignore`）是冲突：保留你的文件，模板版本写在旁边的 `<file>.template-new`，命令以退出码 3 结束。逐个合并后删除 `.template-new`。
   - 若第 1 步也复制了同一发布的 `template-manifest.json`，同样可行：仓库历史中从未有过的托管文件照样新增；已有的同名文件则记为“保留的本地改动”，不写 `.template-new`。
3. 按 `skills/book-new` 补齐 `site.toml` 与 `books/`，运行 `./tbook template status` 与 `./tbook check`，提交。
