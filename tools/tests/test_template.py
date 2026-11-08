"""Tests for template versioning: ``./tbook template status | update | manifest``.

Run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_template.py'

The fixture is a fake template repository built from this repository's managed files
(tagged v0.1.0, then modified and tagged v0.2.0, plus a v0.3.0-rc.1 pre-release) and, per
test, a downstream repository created from v0.1.0 (like GitHub's "Use this template":
a fresh history) with owned changes and local edits to managed files. Updates run against
the template with ``--source <path>``; no network. Git runs with an empty global config.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from tbook import paths, template
from tbook.template import (
    ADD, CONFLICT, KEEP, RELEASE, REMOVE, SAME, SKIP, UPDATE, Manifest, TemplateConfig, TemplateError,
)

REAL_ROOT = paths.ROOT


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r.stdout


def write(path: Path, text: str, mode: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        os.chmod(path, mode)
    return path


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tree_snapshot(root: Path) -> dict[str, tuple[str, str]]:
    """{path: (mode, sha)} of every file and symlink outside .git (for 'nothing changed' checks)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git" and not (Path(dirpath) / d).is_symlink()]
        for name in filenames + [d for d in os.listdir(dirpath) if (Path(dirpath) / d).is_symlink()]:
            p = Path(dirpath) / name
            entry = template.file_entry(p)
            out[p.relative_to(root).as_posix()] = (entry.mode, entry.sha256)
    return out


class GitEnv:
    """Isolate git from the user's global configuration (signing, hooks …)."""

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="tbook-gitcfg-")
        cfg = Path(self.tmp) / "gitconfig"
        cfg.write_text("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n"
                       "[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n", encoding="utf-8")
        self.patch = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1",
                                                  "TBOOK_LANG": "en"})
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------- fixture


MIGRATION_020 = '''\
"""Test migration: records that it ran (idempotent)."""
from pathlib import Path


def migrate(root: Path) -> list[str]:
    marker = root / "books" / "MIGRATED-0.2.0.txt"
    if marker.exists():
        return ["already migrated"]
    marker.write_text("0.2.0\\n", encoding="utf-8")
    return ["wrote books/MIGRATED-0.2.0.txt"]
'''

MIGRATION_OTHER = '''\
from pathlib import Path


def migrate(root: Path) -> list[str]:
    (root / "WRONG-{v}.txt").write_text("must not run", encoding="utf-8")
    return ["ran {v}"]
'''


def copy_real_managed(dest: Path) -> None:
    """This repository's managed files (and the owned files a template repository has)."""
    cfg = TemplateConfig.load(REAL_ROOT)
    files = [p for p in template.candidate_files(REAL_ROOT, cfg) if cfg.manages(p)]
    files += ["template.toml", "site.toml", "README.md", "LICENSE", "trureturing.lock.json"]
    for rel in sorted(set(files)):
        src = REAL_ROOT / rel
        if not os.path.lexists(src):
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            os.symlink(os.readlink(src), dst)
        elif src.is_file():
            shutil.copy2(src, dst)
    for rel in ("books/example-monograph/book.toml", "books/example-monograph/zh/SUMMARY.md"):
        if (REAL_ROOT / rel).exists():
            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REAL_ROOT / rel, dst)


def set_version(root: Path, version: str) -> None:
    p = root / "template.toml"
    text = p.read_text(encoding="utf-8")
    import re

    text, n = re.subn(r'(?m)^version = "[^"]*"', f'version = "{version}"', text, count=1)
    assert n == 1
    p.write_text(text, encoding="utf-8")


def commit_all(root: Path, message: str, tag: str | None = None) -> None:
    template.cmd_manifest(root, out=lambda s: None)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    if tag:
        git(root, "tag", "-a", tag, "-m", tag)


def build_template(base: Path) -> Path:
    tpl = base / "template"
    tpl.mkdir()
    copy_real_managed(tpl)
    set_version(tpl, "0.1.0")
    # Fixture-only files exercising symlinks, modes, removals, conflicts and releases.
    write(tpl / "tools" / "fixture" / "replace.txt", "v1\n")
    write(tpl / "tools" / "fixture" / "remove-me.txt", "bye\n")
    write(tpl / "tools" / "fixture" / "both.txt", "base\n")
    write(tpl / "tools" / "fixture" / "kept.txt", "base\n")
    write(tpl / "tools" / "fixture" / "deleted-locally.txt", "base\n")
    write(tpl / "tools" / "fixture" / "removed-upstream-modified-locally.txt", "base\n")
    write(tpl / "tools" / "fixture" / "deleted-locally-changed-upstream.txt", "base\n")
    write(tpl / "tools" / "fixture" / "to-exec.sh", "#!/bin/sh\necho hi\n", 0o644)
    write(tpl / "tools" / "fixture" / "released.txt", "managed in 0.1.0 only\n")
    os.symlink("replace.txt", tpl / "tools" / "fixture" / "link")
    write(tpl / "docs" / "CHANGELOG.md", textwrap.dedent("""\
        # Changelog

        ## [Unreleased]

        ## [0.1.0] - 2026-11-08

        - First release.
        """))
    git(tpl, "init", "-q", "-b", "main")
    commit_all(tpl, "template 0.1.0", "v0.1.0")
    # A book release tag of the template repository itself: not a template release.
    git(tpl, "tag", "example-monograph-v0.1.0")
    git(tpl, "tag", "vnot-a-version")

    # ---- 0.2.0
    set_version(tpl, "0.2.0")
    fx = tpl / "tools" / "fixture"
    write(fx / "replace.txt", "v2\n")
    (fx / "remove-me.txt").unlink()
    write(fx / "both.txt", "upstream\n")
    (fx / "removed-upstream-modified-locally.txt").unlink()
    write(fx / "deleted-locally-changed-upstream.txt", "upstream\n")
    os.chmod(fx / "to-exec.sh", 0o755)
    write(fx / "new.txt", "new upstream\n")
    write(fx / "new-script.sh", "#!/bin/sh\necho new\n", 0o755)
    write(fx / "new-same.txt", "identical\n")
    write(fx / "new-different.txt", "upstream version\n")
    write(fx / "deep" / "nested" / "file.txt", "deep\n")
    (fx / "link").unlink()
    os.symlink("new.txt", fx / "link")
    os.symlink("deep/nested/file.txt", fx / "new-link")
    # 0.2.0 stops managing tools/fixture/released.txt: it moves under an excluded prefix.
    (fx / "released.txt").unlink()
    text = (tpl / "template.toml").read_text(encoding="utf-8")
    text = text.replace('  "docs/project/",\n]', '  "docs/project/",\n  "tools/fixture/released",\n]')
    (tpl / "template.toml").write_text(text, encoding="utf-8")
    # Owned and excluded paths changed upstream must never reach the downstream.
    write(tpl / "site.toml", (tpl / "site.toml").read_text(encoding="utf-8") + "\n# upstream site change\n")
    write(tpl / "README.md", "# upstream readme\n")
    write(tpl / "skills" / "local-mine" / "SKILL.md", "upstream copy of a local skill\n")
    write(tpl / "docs" / "project" / "notes.md", "upstream project notes\n")
    # Migrations: only v0.2.0 is in (0.1.0, 0.2.0].
    write(tpl / "tools" / "migrations" / "v0.1.0.py", MIGRATION_OTHER.format(v="0.1.0"))
    write(tpl / "tools" / "migrations" / "v0.2.0.py", MIGRATION_020)
    write(tpl / "tools" / "migrations" / "v0.3.0.py", MIGRATION_OTHER.format(v="0.3.0"))
    write(tpl / "docs" / "CHANGELOG.md", textwrap.dedent("""\
        # Changelog

        ## [Unreleased]

        ## [0.2.0] - 2026-11-09

        ### Changed

        - Fixture changes for the update test.

        ## [0.1.0] - 2026-11-08

        - First release.
        """))
    commit_all(tpl, "template 0.2.0", "v0.2.0")

    # ---- 0.3.0-rc.1 (a pre-release: never the default target)
    set_version(tpl, "0.3.0-rc.1")
    write(fx / "replace.txt", "v3-rc\n")
    commit_all(tpl, "template 0.3.0-rc.1", "v0.3.0-rc.1")
    git(tpl, "checkout", "-q", "-b", "next")
    git(tpl, "checkout", "-q", "main")
    return tpl


def make_downstream(base: Path, tpl: Path, name: str = "downstream", tag: str = "v0.1.0",
                    local_work: bool = True) -> Path:
    """A repository created from the template at ``tag`` (fresh history), with typical local work."""
    ds = base / name
    ds.mkdir()
    archive = subprocess.run(["git", "-C", str(tpl), "archive", "--format=tar", tag], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(ds)], input=archive.stdout, check=True)
    git(ds, "init", "-q", "-b", "main")
    git(ds, "add", "-A")
    git(ds, "commit", "-q", "-m", "Initial commit from template")
    if not local_work:
        return ds
    # Owned changes.
    write(ds / "site.toml", "[site]\nlanguages = [\"en\", \"zh\"]\nrepo = \"someone/books\"\n")
    write(ds / "books" / "my-book" / "book.toml", "[book]\nversion = \"1.0.0\"\ntitle = \"Mine\"\n")
    write(ds / "README.md", "# my books\n")
    write(ds / "skills" / "local-mine" / "SKILL.md", "my own skill\n")
    write(ds / "docs" / "project" / "notes.md", "my notes\n")
    # Local edits to managed files.
    fx = ds / "tools" / "fixture"
    write(fx / "both.txt", "local\n")
    write(fx / "kept.txt", "local edit\n")
    (fx / "deleted-locally.txt").unlink()
    write(fx / "removed-upstream-modified-locally.txt", "local\n")
    (fx / "deleted-locally-changed-upstream.txt").unlink()
    write(fx / "new-same.txt", "identical\n")
    write(fx / "new-different.txt", "my version\n")
    write(fx / "released.txt", "managed in 0.1.0 only\n")
    git(ds, "add", "-A")
    git(ds, "commit", "-q", "-m", "Local work")
    return ds


class TemplateFixture(unittest.TestCase):
    """Builds the template repository once per class."""

    @classmethod
    def setUpClass(cls):
        cls.genv = GitEnv().__enter__()
        cls.base = Path(tempfile.mkdtemp(prefix="tbook-template-test-"))
        cls.tpl = build_template(cls.base)
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)
        cls.genv.__exit__(None, None, None)

    def downstream(self, tag: str = "v0.1.0") -> Path:
        type(self).counter += 1
        return make_downstream(self.base, self.tpl, f"downstream-{self.counter}", tag)

    def run_update(self, ds: Path, **kw) -> template.UpdateResult:
        kw.setdefault("source", str(self.tpl))
        return template.update(ds, **kw)

    @staticmethod
    def kinds(res: template.UpdateResult) -> dict[str, str]:
        return {a.path: a.kind for a in res.actions if a.path.startswith("tools/fixture/")}


# --------------------------------------------------------------------------- tests: update


class UpdateTests(TemplateFixture):
    def test_three_way_update(self):
        ds = self.downstream()
        before_owned = {p: (ds / p).read_bytes() for p in ("site.toml", "README.md", "books/my-book/book.toml",
                                                          "skills/local-mine/SKILL.md", "docs/project/notes.md")}
        res = self.run_update(ds)
        self.assertEqual(res.errors, [])
        self.assertEqual((res.old_version, res.new_version), ("0.1.0", "0.2.0"))
        self.assertEqual(res.upstream.ref, "v0.2.0", "the default target is the highest stable release")
        k = self.kinds(res)
        fx = "tools/fixture/"
        expected = {
            "replace.txt": UPDATE,                       # (a) unchanged locally → take upstream
            "remove-me.txt": REMOVE,                     # (a) removed upstream
            "new.txt": ADD,                              # (d) new upstream
            "new-script.sh": ADD,
            "deep/nested/file.txt": ADD,
            "link": UPDATE,                              # retargeted symlink
            "new-link": ADD,
            "to-exec.sh": UPDATE,                        # mode-only change
            "kept.txt": KEEP,                            # (b) modified locally, unchanged upstream
            "deleted-locally.txt": KEEP,
            "both.txt": CONFLICT,                        # (c)
            "removed-upstream-modified-locally.txt": CONFLICT,
            "deleted-locally-changed-upstream.txt": CONFLICT,
            "new-different.txt": CONFLICT,               # (e)
            "new-same.txt": SAME,
            "released.txt": RELEASE,
        }
        for name, kind in expected.items():
            self.assertEqual(k.get(fx + name), kind, name)
        self.assertEqual(res.exit_code, template.EXIT_CONFLICTS)

        f = ds / "tools" / "fixture"
        self.assertEqual((f / "replace.txt").read_text(), "v2\n")
        self.assertFalse((f / "remove-me.txt").exists())
        self.assertEqual((f / "new.txt").read_text(), "new upstream\n")
        self.assertEqual((f / "deep" / "nested" / "file.txt").read_text(), "deep\n")
        # Modes and symlinks.
        self.assertTrue(os.stat(f / "new-script.sh").st_mode & stat.S_IXUSR)
        self.assertTrue(os.stat(f / "to-exec.sh").st_mode & stat.S_IXUSR)
        self.assertFalse(os.stat(f / "new.txt").st_mode & stat.S_IXUSR)
        self.assertTrue((f / "link").is_symlink())
        self.assertEqual(os.readlink(f / "link"), "new.txt")
        self.assertEqual(os.readlink(f / "new-link"), "deep/nested/file.txt")
        self.assertEqual((f / "new-link").read_text(), "deep\n")
        self.assertTrue((ds / "AGENTS.md").is_symlink(), "unchanged symlinks stay symlinks")
        # Kept local changes.
        self.assertEqual((f / "kept.txt").read_text(), "local edit\n")
        self.assertFalse((f / "deleted-locally.txt").exists())
        # Conflicts: local kept, upstream next to it.
        self.assertEqual((f / "both.txt").read_text(), "local\n")
        self.assertEqual((f / "both.txt.template-new").read_text(), "upstream\n")
        self.assertEqual((f / "new-different.txt").read_text(), "my version\n")
        self.assertEqual((f / "new-different.txt.template-new").read_text(), "upstream version\n")
        self.assertEqual((f / "removed-upstream-modified-locally.txt").read_text(), "local\n")
        self.assertFalse((f / "removed-upstream-modified-locally.txt.template-new").exists())
        self.assertFalse((f / "deleted-locally-changed-upstream.txt").exists())
        self.assertEqual((f / "deleted-locally-changed-upstream.txt.template-new").read_text(), "upstream\n")
        # Released and identical files stay.
        self.assertEqual((f / "released.txt").read_text(), "managed in 0.1.0 only\n")
        self.assertEqual((f / "new-same.txt").read_text(), "identical\n")
        # Owned and excluded paths untouched, even though upstream changed them.
        for p, data in before_owned.items():
            self.assertEqual((ds / p).read_bytes(), data, p)
        self.assertTrue((ds / "books" / "my-book" / "book.toml").exists())
        skipped = {a.path for a in res.actions if a.kind == SKIP}
        self.assertNotIn("site.toml", {a.path for a in res.actions if a.kind != SKIP})
        self.assertFalse(any(p.startswith(("skills/local-", "docs/project/")) for p in
                             {a.path for a in res.actions if a.kind != SKIP}))
        self.assertTrue(all(not p.startswith("books/") for p in {a.path for a in res.actions} - skipped))
        # New template.toml and manifest.
        cfg = TemplateConfig.load(ds)
        self.assertEqual(cfg.version, "0.2.0")
        self.assertIn("tools/fixture/released", cfg.exclude)
        manifest = Manifest.load(ds)
        self.assertEqual(manifest.version, "0.2.0")
        self.assertEqual(manifest.files, Manifest.load(self.tpl_at("v0.2.0")).files)
        # Migrations: exactly v0.2.0 ran, from the new template.
        self.assertEqual([m[0] for m in res.migrations], ["v0.2.0.py"])
        self.assertEqual(res.migrations[0][1], ["wrote books/MIGRATED-0.2.0.txt"])
        self.assertTrue((ds / "books" / "MIGRATED-0.2.0.txt").exists())
        self.assertFalse((ds / "WRONG-0.1.0.txt").exists())
        self.assertFalse((ds / "WRONG-0.3.0.txt").exists())

    def tpl_at(self, tag: str) -> Path:
        out = self.base / f"tpl-{tag}"
        if not out.exists():
            out.mkdir()
            archive = subprocess.run(["git", "-C", str(self.tpl), "archive", tag], capture_output=True, check=True)
            subprocess.run(["tar", "-x", "-C", str(out)], input=archive.stdout, check=True)
        return out

    def test_summary_and_exit_code_via_cmd(self):
        ds = self.downstream()
        lines: list[str] = []
        rc = template.cmd_update(ds, to=None, source=str(self.tpl), dry_run=False, force=False, out=lines.append)
        self.assertEqual(rc, 3)
        summary = (ds / "build" / "template-update.md").read_text(encoding="utf-8")
        self.assertIn("## Template update 0.1.0 → 0.2.0", summary)
        self.assertIn("### Conflicts: merge by hand (4)", summary)
        self.assertIn("`tools/fixture/both.txt` — changed locally and upstream; the upstream version is in "
                      "`tools/fixture/both.txt.template-new`", summary)
        self.assertIn("### Added", summary)
        self.assertIn("### Removed", summary)
        self.assertIn("`v0.2.0.py`", summary)
        self.assertIn("wrote books/MIGRATED-0.2.0.txt", summary)
        self.assertIn("## [0.2.0] - 2026-11-09", summary, "the changelog of crossed versions is included")
        self.assertNotIn("## [0.1.0]", summary)
        self.assertIn("docs/CHANGELOG.md", summary)
        self.assertIn("\n".join(lines[:1]), summary)

    def test_summary_in_chinese(self):
        ds = self.downstream()
        write(ds / "site.toml", "[site]\nlanguages = [\"zh\", \"en\"]\n")
        with mock.patch.dict(os.environ, {"TBOOK_LANG": ""}):
            rc = template.cmd_update(ds, to=None, source=str(self.tpl), dry_run=True, force=False,
                                     out=lambda s: None)
            self.assertEqual(rc, 3)
            res = template.update(ds, source=str(self.tpl), dry_run=True)
            text = template.render_summary(res, template._lang(ds))
        self.assertIn("## 模板升级预览 0.1.0 → 0.2.0", text)
        self.assertIn("冲突：需要人工合并", text)
        self.assertIn("将运行：`v0.2.0.py`", text)

    def test_dry_run_writes_nothing(self):
        ds = self.downstream()
        before = tree_snapshot(ds)
        rc = template.cmd_update(ds, to=None, source=str(self.tpl), dry_run=True, force=False, out=lambda s: None)
        self.assertEqual(rc, template.EXIT_CONFLICTS, "a dry run reports the exit code the update would have")
        self.assertEqual(tree_snapshot(ds), before)
        self.assertFalse((ds / "build").exists())
        res = self.run_update(ds, dry_run=True)
        self.assertEqual(res.pending_migrations, ["v0.2.0.py"])
        self.assertEqual(res.migrations, [])
        self.assertIn("Will run: `v0.2.0.py`", template.render_summary(res, "en"))

    def test_force_takes_upstream(self):
        ds = self.downstream()
        write(ds / "tools" / "fixture" / "both.txt.template-new", "stale from an earlier run\n")
        res = self.run_update(ds, force=True)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.conflicts, [])
        f = ds / "tools" / "fixture"
        self.assertEqual((f / "both.txt").read_text(), "upstream\n")
        self.assertFalse((f / "both.txt.template-new").exists())
        self.assertEqual((f / "new-different.txt").read_text(), "upstream version\n")
        self.assertFalse((f / "removed-upstream-modified-locally.txt").exists())
        self.assertEqual((f / "deleted-locally-changed-upstream.txt").read_text(), "upstream\n")
        # --force does not touch files that only changed locally, nor owned paths.
        self.assertEqual((f / "kept.txt").read_text(), "local edit\n")
        self.assertEqual((ds / "README.md").read_text(), "# my books\n")
        forced = [a.path for a in res.actions if a.forced]
        self.assertEqual(len(forced), 4)
        self.assertIn("took the upstream version (--force", template.render_summary(res, "en"))

    def test_second_update_is_a_no_op(self):
        ds = self.downstream()
        self.run_update(ds)
        before = tree_snapshot(ds)
        res = self.run_update(ds)
        self.assertEqual(res.exit_code, 0, "conflicts already written are local changes now")
        self.assertEqual(res.of(ADD, UPDATE, REMOVE, CONFLICT), [])
        self.assertEqual(res.migrations, [], "same version: no migrations")
        before.pop("build/template-update.md", None)
        after = tree_snapshot(ds)
        after.pop("build/template-update.md", None)
        self.assertEqual(after, before)

    def test_to_version_tag_branch_and_commit(self):
        ds = self.downstream()
        res = self.run_update(ds, to="0.1.0", dry_run=True)
        self.assertEqual(res.upstream.ref, "v0.1.0")
        self.assertEqual(res.of(ADD, UPDATE, REMOVE, CONFLICT), [])
        res = self.run_update(ds, to="v0.3.0-rc.1", dry_run=True)
        self.assertEqual(res.new_version, "0.3.0-rc.1")
        self.assertEqual(res.pending_migrations, ["v0.2.0.py"], "0.3.0 > 0.3.0-rc.1: not included")
        res = self.run_update(ds, to="next", dry_run=True)
        self.assertEqual(res.upstream.ref, "next")
        commit = git(self.tpl, "rev-parse", "v0.2.0^{commit}").strip()
        res = self.run_update(ds, to=commit, dry_run=True)
        self.assertEqual(res.upstream.commit, commit)
        self.assertEqual(res.new_version, "0.2.0")
        with self.assertRaisesRegex(TemplateError, "9.9.9 not found"):
            self.run_update(ds, to="9.9.9", dry_run=True)
        with self.assertRaisesRegex(TemplateError, "cannot fetch"):
            self.run_update(ds, to="no-such-branch", dry_run=True)

    def test_upgrade_in_two_steps_runs_each_migration_once(self):
        ds = self.downstream()
        res = self.run_update(ds, to="0.1.0")
        self.assertEqual(res.migrations, [])
        res = self.run_update(ds, to="0.2.0")
        self.assertEqual([m[0] for m in res.migrations], ["v0.2.0.py"])

    def test_no_local_manifest(self):
        ds = self.downstream()
        (ds / "template-manifest.json").unlink()
        res = self.run_update(ds, dry_run=True)
        k = self.kinds(res)
        self.assertEqual(k["tools/fixture/replace.txt"], CONFLICT, "without a base every difference conflicts")
        self.assertEqual(k["tools/fixture/new-same.txt"], SAME)
        self.assertEqual(k["tools/fixture/new.txt"], ADD)
        self.assertTrue(any("no local template-manifest.json" in w for w in res.warnings))

    def test_template_name_mismatch(self):
        ds = self.downstream()
        p = ds / "template.toml"
        p.write_text(p.read_text(encoding="utf-8").replace('name = "trureturing-books-template"',
                                                            'name = "another-template"'), encoding="utf-8")
        with self.assertRaisesRegex(TemplateError, "another-template"):
            self.run_update(ds, dry_run=True)
        res = self.run_update(ds, dry_run=True, force=True)
        self.assertEqual(res.new_version, "0.2.0")

    def test_plain_directory_source(self):
        ds = self.downstream()
        src = self.tpl_at("v0.2.0")
        res = self.run_update(ds, source=str(src), dry_run=True)
        self.assertEqual(res.new_version, "0.2.0")
        self.assertEqual(self.kinds(res)["tools/fixture/both.txt"], CONFLICT)
        with self.assertRaisesRegex(TemplateError, "--to needs a git source"):
            self.run_update(ds, source=str(src), to="0.2.0", dry_run=True)

    def test_not_a_template_source(self):
        ds = self.downstream()
        empty = self.base / "not-a-template"
        empty.mkdir(exist_ok=True)
        with self.assertRaisesRegex(TemplateError, "has no template.toml"):
            self.run_update(ds, source=str(empty))

    def test_no_release_tags(self):
        ds = self.downstream()
        bare = self.base / "untagged"
        if not bare.exists():
            subprocess.run(["git", "clone", "-q", "--no-tags", str(self.tpl), str(bare)], check=True)
            for tag in git(bare, "tag").split():
                git(bare, "tag", "-d", tag)
        with self.assertRaisesRegex(TemplateError, "no release tags vX.Y.Z"):
            self.run_update(ds, source=str(bare))
        res = self.run_update(ds, source=str(bare), to="HEAD", dry_run=True)
        self.assertEqual(res.new_version, "0.3.0-rc.1")

    def test_cli_end_to_end(self):
        """The downstream's own ./tbook (its copy of tools/) performs the update."""
        ds = self.downstream()
        env = dict(os.environ, TBOOK_PYTHON=sys.executable, TBOOK_LANG="en")
        env.pop("TBOOK_ROOT", None)
        r = subprocess.run([str(ds / "tbook"), "template", "update", "--source", str(self.tpl)],
                           cwd=ds, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("Template update 0.1.0 → 0.2.0", r.stdout)
        self.assertTrue((ds / "build" / "template-update.md").exists())
        r = subprocess.run([str(ds / "tbook"), "template", "status"], cwd=ds, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("trureturing-books-template 0.2.0", r.stdout)
        self.assertIn("! tools/fixture/both.txt.template-new", r.stdout)
        r = subprocess.run([str(ds / "tbook"), "template", "update", "--source", str(self.base / "nope")],
                           cwd=ds, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("template: ", r.stderr)


# --------------------------------------------------------------------------- tests: status, manifest


class StatusTests(TemplateFixture):
    def test_status_lists_modified_missing_extra(self):
        ds = self.downstream()
        write(ds / "tools" / "fixture" / "untracked-extra.txt", "x\n")
        write(ds / "skills" / "local-other" / "SKILL.md", "excluded: not extra\n")
        st = template.compute_status(ds)
        self.assertEqual(st.version, "0.1.0")
        self.assertIn("tools/fixture/both.txt", st.modified)
        self.assertIn("tools/fixture/kept.txt", st.modified)
        self.assertIn("tools/fixture/deleted-locally.txt", st.missing)
        self.assertIn("tools/fixture/new-different.txt", st.extra)
        self.assertIn("tools/fixture/untracked-extra.txt", st.extra)
        self.assertFalse(any(p.startswith(("skills/local-", "books/", "docs/project/")) for p in st.extra))
        self.assertNotIn("site.toml", st.modified)
        lines: list[str] = []
        self.assertEqual(template.cmd_status(ds, out=lines.append), 0)
        out = "\n".join(lines)
        self.assertIn("Template: trureturing-books-template 0.1.0", out)
        self.assertIn("  M tools/fixture/both.txt", out)
        self.assertIn("  D tools/fixture/deleted-locally.txt", out)
        self.assertIn("  ? tools/fixture/untracked-extra.txt", out)

    def test_status_clean_and_ignored_files(self):
        ds = make_downstream(self.base, self.tpl, "pristine", local_work=False)
        write(ds / "tools" / "tbook" / "__pycache__" / "x.cpython-313.pyc", "ignored\n")
        st = template.compute_status(ds)
        self.assertEqual((st.modified, st.missing, st.extra, st.pending), ([], [], [], []))
        lines: list[str] = []
        template.cmd_status(ds, out=lines.append)
        self.assertIn("Managed files match the manifest.", lines)

    def test_status_without_manifest(self):
        ds = self.downstream()
        (ds / "template-manifest.json").unlink()
        lines: list[str] = []
        self.assertEqual(template.cmd_status(ds, out=lines.append), 0)
        self.assertIn("No template-manifest.json", "\n".join(lines))


class ManifestTests(TemplateFixture):
    def test_manifest_contents(self):
        m = Manifest.load(self.tpl_dir())
        self.assertEqual(m.schema, template.MANIFEST_SCHEMA)
        self.assertEqual(m.template, "trureturing-books-template")
        self.assertNotIn("template.toml", m.files)
        self.assertNotIn("template-manifest.json", m.files)
        self.assertNotIn("site.toml", m.files)
        self.assertFalse(any(p.startswith(("books/", "skills/local-", "docs/project/")) for p in m.files))
        self.assertEqual(m.files["tbook"].mode, "100755")
        self.assertEqual(m.files["AGENTS.md"].mode, "120000")
        self.assertEqual(m.files["AGENTS.md"].sha256, sha("CLAUDE.md"), "symlinks are hashed by their target")
        self.assertEqual(m.files[".claude/skills"].mode, "120000")
        self.assertEqual(m.files["CLAUDE.md"].mode, "100644")
        self.assertEqual(m.files["CLAUDE.md"].sha256,
                         hashlib.sha256((self.tpl_dir() / "CLAUDE.md").read_bytes()).hexdigest())
        raw = (self.tpl_dir() / "template-manifest.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(list(data), ["schema", "template", "version", "files"])
        self.assertEqual(list(data["files"]), sorted(data["files"]), "paths are sorted")
        self.assertTrue(raw.endswith("}\n"))

    def tpl_dir(self) -> Path:
        out = self.base / "manifest-check"
        if not out.exists():
            subprocess.run(["git", "clone", "-q", str(self.tpl), str(out)], check=True)
            git(out, "checkout", "-q", "v0.1.0")
        return out

    def test_check_detects_stale_manifest(self):
        root = self.base / "manifest-stale"
        subprocess.run(["git", "clone", "-q", str(self.tpl), str(root)], check=True)
        lines: list[str] = []
        self.assertEqual(template.cmd_manifest(root, check=True, out=lines.append), 0, lines)
        write(root / "docs" / "CHANGELOG.md", "changed\n")
        write(root / "tools" / "brand-new.py", "x = 1\n")  # untracked, not ignored: counts
        write(root / "tools" / "tbook" / "__pycache__" / "y.pyc", "ignored\n")
        (root / "docs" / "AUTHORING.md").unlink()
        os.chmod(root / "docs" / "PUBLISHING.md", 0o755)
        set_version(root, "0.4.0")
        lines = []
        self.assertEqual(template.cmd_manifest(root, check=True, out=lines.append), 1)
        out = "\n".join(lines)
        self.assertIn("out of date", out)
        self.assertIn("  ~ docs/CHANGELOG.md", out)
        self.assertIn("  + tools/brand-new.py", out)
        self.assertIn("  - docs/AUTHORING.md", out)
        self.assertIn("  ~ docs/PUBLISHING.md (mode 100644 → 100755)", out)
        self.assertIn("  version: 0.3.0-rc.1 → 0.4.0", out)
        self.assertNotIn("pyc", out)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(template.cmd_manifest(root, out=lambda s: None), 0)
        self.assertEqual(template.cmd_manifest(root, check=True, out=lambda s: None), 0)
        self.assertEqual(Manifest.load(root).version, "0.4.0")

    def test_manifest_without_git_walks_the_tree(self):
        root = self.base / "manifest-nogit"
        if not root.exists():
            shutil.copytree(self.tpl_at_plain(), root, symlinks=True)
        write(root / "tools" / "tbook" / "__pycache__" / "z.pyc", "skipped\n")
        cfg = TemplateConfig.load(root)
        walked = template.build_manifest(root, cfg)
        self.assertEqual(walked.files, Manifest.load(root).files)

    def tpl_at_plain(self) -> Path:
        out = self.base / "plain-v0.1.0"
        if not out.exists():
            out.mkdir()
            archive = subprocess.run(["git", "-C", str(self.tpl), "archive", "v0.1.0"], capture_output=True,
                                     check=True)
            subprocess.run(["tar", "-x", "-C", str(out)], input=archive.stdout, check=True)
        return out

    def test_unreadable_manifest(self):
        root = self.base / "manifest-bad"
        subprocess.run(["git", "clone", "-q", str(self.tpl), str(root)], check=True)
        write(root / "template-manifest.json", '{"schema": "something-else"}')
        lines: list[str] = []
        self.assertEqual(template.cmd_manifest(root, check=True, out=lines.append), 1)
        self.assertIn("unsupported schema", "\n".join(lines))


# --------------------------------------------------------------------------- unit tests (no repositories)


class UnitTests(unittest.TestCase):
    def test_semver_order(self):
        versions = ["0.10.0", "0.2.0", "1.0.0", "1.0.0-rc.1", "1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10",
                    "0.2.1", "1.0.0-beta"]
        ordered = sorted(versions, key=template.parse_semver)
        self.assertEqual(ordered, ["0.2.0", "0.2.1", "0.10.0", "1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10",
                                   "1.0.0-beta", "1.0.0-rc.1", "1.0.0"])
        self.assertIsNone(template.parse_semver("1.0"))
        self.assertIsNone(template.parse_semver("v1.0.0"))
        self.assertEqual(template.parse_semver("1.2.3+build.5"), template.parse_semver("1.2.3"))
        self.assertTrue(template.is_prerelease("1.0.0-rc.1"))
        self.assertFalse(template.is_prerelease("1.0.0"))

    def test_release_tags_and_targets(self):
        tags = {"v0.1.0": "a", "v0.10.0": "b", "v0.9.0": "c", "v1.0.0-rc.1": "d", "book-v2.0.0": "e", "vX": "f"}
        self.assertEqual([t for t, _ in template.release_tags(tags, "v")],
                         ["v0.1.0", "v0.9.0", "v0.10.0", "v1.0.0-rc.1"])
        self.assertEqual(template.resolve_target(None, tags, "v", "src"), ("refs/tags/v0.10.0", "v0.10.0"))
        self.assertEqual(template.resolve_target("0.9.0", tags, "v", "src"), ("refs/tags/v0.9.0", "v0.9.0"))
        self.assertEqual(template.resolve_target("v1.0.0-rc.1", tags, "v", "src")[1], "v1.0.0-rc.1")
        self.assertEqual(template.resolve_target("main", tags, "v", "src"), ("main", "main"))
        with self.assertRaises(TemplateError):
            template.resolve_target("2.0.0", tags, "v", "src")
        with self.assertRaises(TemplateError):
            template.resolve_target(None, {"v1.0.0-rc.1": "d"}, "v", "src")
        self.assertEqual(template.resolve_target(None, {"release-1.2.3": "x"}, "release-", "src")[1], "release-1.2.3")

    def test_path_rules(self):
        cfg = TemplateConfig(name="t", repo="o/r", version="1.0.0",
                             managed=["tools/", "tbook", "docs/", ".github/workflows/"],
                             owned=["books/", "site.toml"], exclude=["skills/local-", "docs/project/"])
        self.assertTrue(cfg.manages("tools/tbook/cli.py"))
        self.assertTrue(cfg.manages("tbook"))
        self.assertFalse(cfg.manages("tbook-extra"))
        self.assertFalse(cfg.manages("toolsx/a"))
        self.assertTrue(cfg.manages("docs/AUTHORING.md"))
        self.assertFalse(cfg.manages("docs/project/notes.md"))
        self.assertTrue(cfg.is_excluded("skills/local-mine/SKILL.md"))
        self.assertFalse(cfg.manages("books/x/book.toml"))
        self.assertFalse(cfg.manages("template.toml"))
        self.assertFalse(cfg.manages("tools/a.py.template-new"))
        self.assertTrue(cfg.protects("site.toml"))
        self.assertTrue(cfg.protects("docs/project/a.md"))
        self.assertFalse(cfg.protects("docs/a.md"))

    def test_config_errors(self):
        with self.assertRaisesRegex(TemplateError, "version is required"):
            TemplateConfig.from_bytes(b"[template]\nname='x'\n[managed]\npaths=['a/']\n")
        with self.assertRaisesRegex(TemplateError, "paths is required"):
            TemplateConfig.from_bytes(b"[template]\nversion='1.0.0'\n")
        with self.assertRaisesRegex(TemplateError, "list of strings"):
            TemplateConfig.from_bytes(b"[template]\nversion='1.0.0'\n[managed]\npaths=['a/']\nowned='x'\n")
        with self.assertRaisesRegex(TemplateError, "template.toml"):
            TemplateConfig.from_bytes(b"[template\n")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(TemplateError, "docs/UPGRADING.md"):
                TemplateConfig.load(Path(tmp))

    def test_changelog_sections(self):
        text = textwrap.dedent("""\
            # Changelog

            intro

            ## [Unreleased]

            - pending

            ## [0.3.0] - 2026-12-01

            - three

            ## [0.2.0] - 2026-11-20

            - two

            ## [0.1.0] - 2026-11-08

            - one
            """)
        out = template.changelog_sections(text, "0.1.0", "0.3.0")
        self.assertIn("## [0.3.0]", out)
        self.assertIn("- two", out)
        self.assertNotIn("one", out)
        self.assertNotIn("pending", out)
        self.assertNotIn("intro", out)
        self.assertEqual(template.changelog_sections(text, "0.3.0", "0.3.0"), "")

    def test_find_migrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name in ("v0.1.0.py", "v0.2.0.py", "v0.10.0.py", "v1.0.0-rc.1.py", "v1.0.0.py", "README.md",
                         "helper.py", "v2.py"):
                write(d / name, "def migrate(root):\n    return []\n")
            names = [m.name for m in template.find_migrations(d, "0.1.0", "1.0.0")]
            self.assertEqual(names, ["v0.2.0.py", "v0.10.0.py", "v1.0.0-rc.1.py", "v1.0.0.py"])
            self.assertEqual(template.find_migrations(d, "1.0.0", "0.2.0"), [], "no migrations on a downgrade")
            self.assertEqual(template.find_migrations(d, "dev", "1.0.0"), [])
            write(d / "v3.0.0.py", "x = 1\n")
            mig = template.find_migrations(d, "2.0.0", "3.0.0")[0]
            with self.assertRaisesRegex(TemplateError, "no migrate"):
                template.run_migration(mig, d)
            write(d / "v3.0.0.py", "def migrate(root):\n    return 'one note'\n")
            self.assertEqual(template.run_migration(mig, d), ["one note"])

    def test_file_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write(d / "a.txt", "hello", 0o644)
            write(d / "b.sh", "#!/bin/sh\n", 0o755)
            os.symlink("a.txt", d / "link")
            os.symlink("missing-target", d / "dangling")
            (d / "dir").mkdir()
            self.assertEqual(template.file_entry(d / "a.txt"), template.Entry(sha("hello"), "100644"))
            self.assertEqual(template.file_entry(d / "b.sh").mode, "100755")
            self.assertEqual(template.file_entry(d / "link"), template.Entry(sha("a.txt"), "120000"))
            self.assertEqual(template.file_entry(d / "dangling"), template.Entry(sha("missing-target"), "120000"))
            self.assertEqual(template.file_entry(d / "dir").mode, template.MODE_OTHER)
            self.assertIsNone(template.file_entry(d / "nope"))

    def test_main_dispatch_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = mock.Mock(template_cmd="status")
            with mock.patch.object(paths, "ROOT", Path(tmp)), redirect_stderr(io.StringIO()) as err:
                self.assertEqual(template.main(args), 1)
            self.assertIn("template.toml not found", err.getvalue())
            with redirect_stderr(io.StringIO()):
                self.assertEqual(template.main(mock.Mock(template_cmd="bogus")), 1)

    def test_language_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(os.environ, {"TBOOK_LANG": ""}):
                self.assertEqual(template._lang(root), "en")
                write(root / "site.toml", '[site]\nlanguages = ["zh-Hant", "en"]\n')
                self.assertEqual(template._lang(root), "zh")
                write(root / "site.toml", '[site]\nlanguages = ["fr", "en"]\n')
                self.assertEqual(template._lang(root), "en")
            with mock.patch.dict(os.environ, {"TBOOK_LANG": "zh"}):
                self.assertEqual(template._lang(root), "zh")
        for lang in template.STRINGS:
            self.assertEqual(set(template.STRINGS[lang]), set(template.STRINGS["en"]), lang)


class RealRepositoryTests(unittest.TestCase):
    """Properties of this repository's own template.toml / manifest."""

    def test_real_template_toml(self):
        cfg = TemplateConfig.load(REAL_ROOT)
        self.assertEqual(cfg.tag_prefix, "v")
        self.assertIsNotNone(template.parse_semver(cfg.version))
        for owned in ("books/", "site.toml", "trureturing.lock.json"):
            self.assertIn(owned, cfg.owned)
            self.assertFalse(cfg.manages(owned))
        self.assertTrue(cfg.manages("tools/tbook/template.py"))
        self.assertTrue(cfg.manages(".github/workflows/ci.yml"))

    # CONFIG GAP (template.toml): the workflows use the composite action .github/actions/setup, which is
    # not under [managed].paths, so template updates would never deliver changes to it.
    # Patch: add ".github/actions/" after ".github/workflows/" in template.toml [managed].paths
    # (and in docs/UPGRADING.md §1).
    def test_setup_action_is_managed(self):
        self.assertTrue(TemplateConfig.load(REAL_ROOT).manages(".github/actions/setup/action.yml"))

    def test_real_manifest_is_well_formed(self):
        m = Manifest.load(REAL_ROOT)
        if m is None:
            self.skipTest("template-manifest.json not generated yet")
        cfg = TemplateConfig.load(REAL_ROOT)
        self.assertEqual(m.template, cfg.name)
        for p, e in m.files.items():
            self.assertTrue(cfg.manages(p), p)
            self.assertIn(e.mode, ("100644", "100755", "120000"), p)
            self.assertRegex(e.sha256, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
