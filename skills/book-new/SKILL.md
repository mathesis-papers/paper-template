---
name: book-new
description: 在书库中新建一本书、新增章节或新增一个语言版本时使用（./tbook new-book / new-chapter），包括 book.toml 元数据、默认中英双语与 SUMMARY 结构。
---

# 新建书、章节与语言版本

## 适用范围

**用**：开一本新书；给已有书加章节；给书加一种语言（如日文）；从模板仓库新建下游书库后的初始化。

**不用**：写章节内容（`skills/book-write`）。

## 新书库（从模板创建后）

1. 在 GitHub 上用 “Use this template” 创建仓库，克隆到本地。
2. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && npm ci`；`./tbook doctor` 逐项检查工具链并给出修复命令。
3. 编辑 `site.toml`：站点标题、`languages`（默认 `["zh", "en"]`）、`[books].order`。`repo` 与 `base_url` 一般留空（自动推断）。
4. 示例书 `books/example-monograph/` 可以保留作参考，或删除整个目录并从 `site.toml` 的 `order` 中去掉。
5. 在 GitHub：Settings → Pages → Source 选 “GitHub Actions”。
6. `./tbook check && ./tbook build all`，`./tbook serve` 本地预览。

## 新书

```bash
./tbook new-book <slug> --title zh="中文书名" --title en="English Title" \
  [--subtitle zh=… --subtitle en=…] [--langs zh,en] [--author "…"] [--code "CODE//NAME"]
```

- `<slug>`：kebab-case，是目录名、URL 段与下载文件名前缀，发布后不要改。
- 生成 `books/<slug>/{book.toml, zh/, en/, assets/}`。补全 `book.toml` 的 `description`、`license`、可选 `isbn`；`code` 是封面与站点卡片上的赛博朋克代号。
- 把 `<slug>` 加入 `site.toml` 的 `[books].order`。

## 新章节

```bash
./tbook new-chapter <slug> ch02-name --title zh="第二章 …" --title en="Chapter 2 …"
```

会在每个语言版本的 `SUMMARY.md` 末尾追加条目并创建文件。如果 SUMMARY 末尾有附录类（无编号）章节，请手动把新条目移到编号列表里。嵌套小节：在 SUMMARY 中缩进两个空格。

## 新语言版本

1. 在 `book.toml` 的 `editions` 中加入语言代码（如 `"ja"`）；第一个仍是权威版本。
2. 若 `theme/i18n/<lang>.toml` 不存在：复制 `theme/i18n/en.toml` 到仓库根的 `i18n/<lang>.toml` 并翻译（`meta.bcp47` 设为正确的 BCP 47 标签，如 `ja`）。
3. 把它加入 `site.toml` 的 `languages`（站点界面也会提供该语言）。
4. 复制权威版本目录为 `books/<slug>/<lang>/`，保持文件名与环境序列不变，逐章翻译。
5. `./tbook check` 校验对齐。

## 完成标准

`./tbook check` 0 错误；`./tbook build html --book <slug>` 成功；书库首页出现新书卡片。
