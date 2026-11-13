## 模板升级 0.3.1 → 0.4.0

来源：`/Users/lexa/Desktop/lexa/omega/mathesis-paper-template` @ `layer/mathesis-0.4.0-upstream-0.8.2` (`af3d76085a17`)

新增 0 · 更新 7 · 删除 0 · 冲突 0 · 保留本地改动 0

### 更新（7）

- `docs/layer-mathesis/CHANGELOG.md`
- `docs/layer-mathesis/README.md`
- `docs/layer-mathesis/UPSTREAM-PINS.md`
- `docs/layer-mathesis/scripts/paper.py`
- `docs/layer-mathesis/tests/test_paper.py`
- `skills/layer-mathesis-paper-book/SKILL.md`
- `skills/layer-mathesis-paper-sync/SKILL.md`

### 迁移

无需迁移。

### 变更记录

阅读跨越的各版本说明，处理标为“需要手动操作”的条目：`docs/layer-mathesis/CHANGELOG.md`

<details>
<summary>docs/layer-mathesis/CHANGELOG.md</summary>

## [0.4.0] - 2026-11-13

- Require upstream trureturing-books-template ≥ 0.8.2 and retire all temporary PR-head pins.
- Confirm that the release includes written-proof academic citations and the active-root film fixture correction; use upstream managed files without compatibility patches.
- Document the released DOI, source-location and registered formalization-request contract for written proofs, and adapt the offline layer fixture to it.

</details>

### 下一步

1. 重新安装依赖：`pip install -r requirements.txt`、`npm ci`。
2. 验证：`./tbook doctor`、`./tbook check`、`./tbook build all`，并运行单元测试。
