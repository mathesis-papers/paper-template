# 模板升级 · Upgrading the template

本书库基于 [trureturing-books-template](https://github.com/the-omega-institute/trureturing-books-template)。模板以语义化版本发布（tag `vX.Y.Z`），下游书库通过 `./tbook template update` 升级。

## 1. 托管与自有

`template.toml` 定义了边界：

- **托管**（`[managed].paths`）：`tools/`、`theme/`、`templates/`、`skills/`、`docs/`、`.github/workflows/`、`.claude/`、`CLAUDE.md`、`AGENTS.md`、`tbook`、`template.toml`、`template-manifest.json`、`requirements.txt`、`package.json`、`package-lock.json`、`.gitignore`、`.editorconfig`。升级时同步（新增、修改、删除）。
- **例外**（`[managed].exclude`）：`skills/local-*`（书库自己的 skill）、`docs/project/`（书库自己的文档）。
- **自有**：`books/`、`site.toml`、`trureturing.lock.json`、`i18n/`、`PROJECT.md`、`README.md`、`LICENSE`，以及任何不在托管路径下的文件。升级永不触碰。

`template-manifest.json` 记录当前版本每个托管文件的 sha256 与权限位，用来判断“本地是否改过”。

## 2. 升级

```bash
./tbook template status              # 当前版本；本地改过、缺失、多出的托管文件
./tbook template update --dry-run    # 预览到最新版本的变化
./tbook template update              # 执行；--to vX.Y.Z 指定版本；--source <路径或 git URL> 指定来源
```

每个托管文件按三方比较处理（基准是本地清单记录的旧版本）：

| 本地 | 上游 | 结果 |
| --- | --- | --- |
| 未改 | 改了 / 新增 / 删除 | 采用上游 |
| 改了 | 未改 | 保留本地 |
| 改了 | 改了 | **冲突**：保留本地，上游版本写入 `<file>.template-new` |

有冲突时命令以退出码 3 结束。逐个合并后删除 `.template-new` 文件。`--force` 直接采用上游（会丢弃本地改动，慎用）。

升级完成后会运行 `tools/migrations/` 中跨越版本的迁移脚本，并把摘要写到 `build/template-update.md`。然后：

```bash
.venv/bin/pip install -r requirements.txt && npm ci
./tbook doctor && ./tbook check && ./tbook build all
```

## 3. 自动升级 PR

`.github/workflows/template-sync.yml` 每周检查模板的新版本，执行升级并开 PR（分支 `template-update/<version>`）。用 `GITHUB_TOKEN` 开的 PR 不会触发其他工作流；若希望 CI 自动跑，在仓库 Secrets 中设置 `BOT_TOKEN`（有 `contents` 与 `pull-requests` 写权限的令牌）。

## 4. 改进托管文件

不要在书库中长期修改托管文件：把改进提交到模板仓库（流程见 `skills/template-update/SKILL.md` 的 B 节），发布新版本后再升级回来。

## 5. 不是从模板创建的仓库

已有仓库也可以接入：复制 `tbook`、`tools/`、`template.toml`、`template-manifest.json` 后运行 `./tbook template update --source https://github.com/the-omega-institute/trureturing-books-template.git`，再按 `skills/book-new` 补齐 `site.toml` 与 `books/`。
