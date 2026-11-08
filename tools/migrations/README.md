# 模板迁移脚本 · Template migrations

`./tbook template update` 把托管文件同步到模板的新版本之后，会运行本目录中**跨越的版本**的迁移脚本，用来改写书库自己的内容（`books/`、`site.toml`、`i18n/` …）——这些路径模板更新永远不会直接覆盖，只能由迁移脚本有意识地修改。

After `./tbook template update` has synchronised the managed files, it runs the migration of every version it crossed. Migrations are the only way a template release changes repository-owned content (books, `site.toml`, `i18n/`).

## 约定 · Convention

- **文件名**：`v<X.Y.Z>.py`，与模板版本（`template.toml` 的 `[template].version`）一致，例如 `v0.2.0.py`、`v1.0.0-rc.1.py`。其他文件（本 README、`_helpers.py` 之类）不会被当作迁移运行。
- **范围**：从版本 `old` 升级到 `new` 时，运行所有满足 `old < X.Y.Z ≤ new` 的迁移，按语义化版本从低到高依次执行。降级与同版本更新不运行迁移。
- **来源**：迁移脚本取自**新版本**模板（升级时抓取的那一份），而不是书库里可能被改过的旧副本。
- **接口**：每个文件定义

  ```python
  from pathlib import Path

  def migrate(root: Path) -> list[str]:
      """root 是书库根目录。返回给人看的说明（每条一行），写进升级摘要。"""
  ```

  返回值也可以是 `None`（无说明）或单个字符串。
- **幂等**：同一迁移可能运行多次（例如中途失败后重跑、或者两个分支各自升级），必须能安全地重复执行；已经迁移过就返回 `["already migrated"]` 一类的说明。
- **只用标准库**：迁移在依赖重新安装之前运行（`pip install -r requirements.txt` 是升级后的下一步），不能导入 `pypandoc`、`typst` 等第三方包。可以导入 `tbook` 的纯 Python 模块，但要注意它此时已经是新版本。
- **只改书库自有内容**：托管文件已经由三方合并处理，迁移不要改它们。改动应尽量机械、可审阅；无法自动处理的情况写成说明，交给人工（升级 PR 的正文会列出这些说明）。
- **失败**：抛出异常即视为失败。`update` 停止运行后续迁移、在摘要中报告错误并以退出码 1 结束；此时托管文件与 `template.toml` 已经是新版本，修复问题后可以手动重跑：

  ```bash
  PYTHONPATH=tools python3 -c "from pathlib import Path; import runpy; runpy.run_path('tools/migrations/v0.2.0.py')['migrate'](Path('.'))"
  ```

- **记录**：在 `docs/CHANGELOG.md` 对应版本下写明迁移做了什么、还需要哪些手动操作（标为“需要手动操作”）。破坏性变更（需要下游改内容或配置）提升 MAJOR 版本并必须提供迁移。

## 示例 · Example

```python
"""v0.2.0: book.toml 的 [outputs].pdf 由布尔值改为变体列表。"""

from __future__ import annotations

import re
from pathlib import Path


def migrate(root: Path) -> list[str]:
    notes: list[str] = []
    for toml in sorted((root / "books").glob("*/book.toml")):
        text = toml.read_text(encoding="utf-8")
        new = re.sub(r"(?m)^pdf\s*=\s*true\s*$", 'pdf = ["screen", "print"]', text)
        if new != text:
            toml.write_text(new, encoding="utf-8")
            notes.append(f"{toml.relative_to(root)}: outputs.pdf = true → [\"screen\", \"print\"]")
    return notes or ["nothing to migrate"]
```

## 测试 · Testing

在模板仓库中为每个迁移写单元测试（`tools/tests/`）：在临时目录里构造旧格式的书库，运行 `migrate()` 两次，断言结果正确且第二次不再改动。`tools/tests/test_template.py` 演示了迁移在升级流程中的运行方式（范围、顺序、来源）。
