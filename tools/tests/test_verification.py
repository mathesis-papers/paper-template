"""Regression tests of the verification chain: branch ancestry of the pinned commit, GID syntax,
declaration lines, pin reports and the checks that compare editions and lock entries.

Run: PYTHONPATH=tools python -m unittest discover -s tools/tests -p 'test_verification.py'

Like ``test_core`` (whose fixtures are reused), every test runs in a throwaway books repository
and replaces trureturing with ``FakeLedger`` or with small git repositories made on the fly.
Nothing touches the network: GitHub's API is replaced by a fake ``urlopen``. Tests against the
real trureturing checkout are skipped when it (or the pinned commit) is absent.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tbook import check, config, lean, model, paths, pin
from test_core import (COMMIT, EN_SUMMARY, GID_3V, GID_DEF, GID_INT, MOD_3V, OLD_COMMIT, TRU,
                       ZH_SUMMARY, CoreRepo, FakeLedger, lock_decls, make_lock, media_stub, messages, name_key,
                       states, write)

GIT_ENV = dict(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
UPSTREAM = f"https://github.com/{TRU}.git"
# The trureturing commit the real-ledger examples below were taken from (independent of this repository's lock).
REAL_COMMIT = "8a24ea4e79de962725aab9d9b49cc605fcc211d8"


def real_checkout() -> Path | None:
    """A local trureturing checkout that has ``REAL_COMMIT`` (``$TRURETURING_DIR`` or ``../trureturing``)."""
    for cand in (os.environ.get("TRURETURING_DIR"), paths.ROOT.parent / "trureturing"):
        if not cand or not (Path(cand) / ".git").exists():
            continue
        r = subprocess.run(["git", "-C", str(cand), "cat-file", "-e", f"{REAL_COMMIT}^{{commit}}"], capture_output=True)
        if r.returncode == 0:
            return Path(cand)
    return None


REAL = real_checkout()


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], env=dict(os.environ, **GIT_ENV), capture_output=True,
                       text=True)
    if r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


class History:
    """A trureturing stand-in: ``dev`` = A ← B, and an unmerged commit C on top of A (a PR head)."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="tbook-tru-")
        self.dir = d = Path(self._tmp.name)
        git(d, "init", "-q")
        git(d, "symbolic-ref", "HEAD", "refs/heads/dev")
        write(d / f"Golden/Frozen/state/{MOD_3V}.lean.json", json.dumps(states()[MOD_3V]))
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "A")
        self.a = git(d, "rev-parse", "HEAD")
        git(d, "commit", "-q", "--allow-empty", "-m", "B")
        self.b = git(d, "rev-parse", "HEAD")
        git(d, "checkout", "-q", "-b", "pr", self.a)
        git(d, "commit", "-q", "--allow-empty", "-m", "C")
        self.c = git(d, "rev-parse", "HEAD")
        git(d, "checkout", "-q", "dev")

    def track(self, remote: str, url: str, branch: str = "dev", at: str | None = None) -> None:
        git(self.dir, "remote", "add", remote, url)
        git(self.dir, "update-ref", f"refs/remotes/{remote}/{branch}", at or self.b)

    def cleanup(self):
        self._tmp.cleanup()


class FakeResponse:
    def __init__(self, data: dict, status: int = 200):
        self.status, self._body = status, json.dumps(data).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeGitHub:
    """``urllib.request.urlopen`` stand-in answering api.github.com paths from a dict."""

    def __init__(self, answers: dict[str, dict | int]):
        self.answers = answers
        self.requests: list = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        path = req.full_url.removeprefix("https://api.github.com/")
        answer = self.answers.get(path, 404)
        if isinstance(answer, int):
            raise urllib.error.HTTPError(req.full_url, answer, "error", {},
                                         io.BytesIO(json.dumps({"message": f"status {answer}"}).encode()))
        return FakeResponse(answer)


def compare_path(branch: str, commit: str) -> str:
    return f"repos/{TRU}/compare/{branch}...{commit}"


# --------------------------------------------------------------------------- finding 0: branch ancestry


class GitAncestryTests(unittest.TestCase):
    def setUp(self):
        self.h = History()
        self.addCleanup(self.h.cleanup)

    def test_remote_tracking_ref_of_the_configured_repository(self):
        h = self.h
        h.track("upstream", UPSTREAM)
        self.assertEqual(lean._branch_ref(h.dir, TRU, "dev"), "refs/remotes/upstream/dev")
        yes = lean.git_branch_contains(h.dir, TRU, "dev", h.a)
        self.assertEqual(yes.on_branch, True)
        self.assertIn("upstream/dev", yes.detail)
        self.assertTrue(lean.git_branch_contains(h.dir, TRU, "dev", h.b).on_branch, "the head itself")
        no = lean.git_branch_contains(h.dir, TRU, "dev", h.c)
        self.assertIs(no.on_branch, False, "an unmerged commit (e.g. a pull-request head) is not on dev")
        self.assertIn("fetch", no.detail)
        unknown = lean.git_branch_contains(h.dir, TRU, "dev", "f" * 40)
        self.assertIsNone(unknown.on_branch)
        self.assertIsNone(lean.git_branch_contains(h.dir, TRU, "main", h.a).on_branch, "no such branch")

    def test_origin_and_local_branch_fallbacks(self):
        h = self.h
        self.assertEqual(lean._branch_ref(h.dir, TRU, "dev"), "refs/heads/dev", "no remotes: the local branch")
        h.track("origin", "https://example.org/mirror/trureturing.git", at=h.a)
        self.assertEqual(lean._branch_ref(h.dir, TRU, "dev"), "refs/remotes/origin/dev")
        self.assertIs(lean.git_branch_contains(h.dir, TRU, "dev", h.b).on_branch, False,
                      "origin/dev (at A) wins over the local dev (at B)")
        h.track("gh", f"git@github.com:{TRU}")
        self.assertEqual(lean._branch_ref(h.dir, TRU, "dev"), "refs/remotes/gh/dev", "the remote of the repository")

    def test_same_repo_urls(self):
        for url in (UPSTREAM, f"https://github.com/{TRU}", f"git@github.com:{TRU}.git", f"HTTPS://GitHub.com/{TRU}/"):
            self.assertTrue(lean._same_repo(url, TRU), url)
        for url in (f"https://github.com/{TRU}-fork.git", "https://github.com/someone/trureturing.git", "/srv/tru"):
            self.assertFalse(lean._same_repo(url, TRU), url)


class LedgerAncestryTests(unittest.TestCase):
    def setUp(self):
        self.repo = CoreRepo().__enter__()
        self.addCleanup(self.repo.__exit__, None, None, None)
        self.h = History()
        self.addCleanup(self.h.cleanup)
        self.h.track("origin", UPSTREAM)

    def github(self, answers):
        fake = FakeGitHub(answers)
        patcher = mock.patch.object(lean.urllib.request, "urlopen", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_checkout_answers_and_positive_answers_are_cached(self):
        h = self.h
        gh = self.github({})
        led = lean.Ledger(TRU, offline=True, checkout=h.dir)
        self.assertTrue(led.branch_contains(h.a, "dev").on_branch)
        marker = paths.CACHE / "trureturing" / h.a / lean.ANCESTRY_FILE
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8")),
                         {f"{TRU}@dev": f"ancestor of origin/dev in {h.dir}"})
        self.assertIs(led.branch_contains(h.c, "dev").on_branch, False)
        self.assertFalse((paths.CACHE / "trureturing" / h.c / lean.ANCESTRY_FILE).exists(), "no negative cache")
        cached = lean.Ledger(TRU, offline=True).branch_contains(h.a, "dev")  # no checkout, no network
        self.assertEqual((cached.on_branch, cached.detail.endswith("(cached)")), (True, True))
        self.assertIsNone(lean.Ledger(TRU, offline=True).branch_contains(h.a, "main").on_branch,
                          "the cache is per branch")
        self.assertEqual(gh.requests, [], "offline: no API request")

    def test_offline_without_checkout_cannot_tell(self):
        res = lean.Ledger(TRU, offline=True).branch_contains(COMMIT, "dev")
        self.assertIsNone(res.on_branch)
        self.assertIn("no local trureturing checkout", res.detail)
        self.assertIn("network disabled", res.detail)

    def test_github_compare(self):
        gh = self.github({compare_path("dev", COMMIT): {"status": "behind", "ahead_by": 0, "behind_by": 3},
                          compare_path("dev", OLD_COMMIT): {"status": "diverged", "ahead_by": 2, "behind_by": 9},
                          compare_path("dev", "c" * 40): {"status": "ahead", "ahead_by": 1, "behind_by": 0},
                          compare_path("dev", "d" * 40): {"status": "identical", "ahead_by": 0, "behind_by": 0},
                          compare_path("dev", "e" * 40): 403,
                          compare_path("release/1", COMMIT): {"status": "behind"}})
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GH_TOKEN", None)
        os.environ["TRURETURING_TOKEN"] = "tok"
        led = lean.Ledger(TRU)
        self.assertTrue(led.branch_contains(COMMIT, "dev").on_branch)
        req = gh.requests[0]
        self.assertEqual(req.full_url, f"https://api.github.com/{compare_path('dev', COMMIT)}")
        self.assertEqual(req.get_header("Authorization"), "Bearer tok")
        no = led.branch_contains(OLD_COMMIT, "dev")
        self.assertIs(no.on_branch, False)
        self.assertIn("diverged, 2 commit(s) not on dev", no.detail)
        self.assertIs(led.branch_contains("c" * 40, "dev").on_branch, False, "ahead of dev: not merged yet")
        self.assertTrue(led.branch_contains("d" * 40, "dev").on_branch, "the head of dev")
        limited = led.branch_contains("e" * 40, "dev")
        self.assertIsNone(limited.on_branch)
        self.assertIn("HTTP 403 status 403", limited.detail)
        missing = led.branch_contains("f" * 40, "dev")
        self.assertIsNone(missing.on_branch)
        self.assertIn("unknown commit", missing.detail)
        self.assertTrue(led.branch_contains(COMMIT, "release/1").on_branch, "slashes in branch names")
        os.environ.pop("TRURETURING_TOKEN")
        os.environ["GITHUB_TOKEN"] = "gh"
        gh.requests.clear()
        lean.Ledger(TRU).branch_contains(OLD_COMMIT, "dev")
        self.assertEqual(gh.requests[0].get_header("Authorization"), "Bearer gh")
        os.environ.pop("GITHUB_TOKEN")
        gh.requests.clear()
        lean.Ledger(TRU).branch_contains(OLD_COMMIT, "dev")
        self.assertIsNone(gh.requests[0].get_header("Authorization"))

    def test_github_overrides_a_stale_checkout_and_a_checkout_no_stands_alone(self):
        h = self.h
        git(h.dir, "update-ref", "refs/remotes/origin/dev", h.a)  # stale: dev has moved to B since the last fetch
        gh = self.github({compare_path("dev", h.b): {"status": "identical"}})
        led = lean.Ledger(TRU, checkout=h.dir)
        self.assertTrue(led.branch_contains(h.b, "dev").on_branch)
        self.assertEqual(len(gh.requests), 1)
        no = led.branch_contains(h.c, "dev")  # GitHub does not know C (404): the checkout's answer stands
        self.assertIs(no.on_branch, False)
        self.assertIn("not an ancestor of origin/dev", no.detail)
        gh.requests.clear()
        self.assertTrue(led.branch_contains(h.a, "dev").on_branch)
        self.assertEqual(gh.requests, [], "a checkout's yes needs no API request")

    def test_ancestry_required(self):
        os.environ.pop("GITHUB_ACTIONS", None)
        self.assertFalse(lean.ancestry_required(False))
        os.environ["GITHUB_ACTIONS"] = "true"
        self.assertTrue(lean.ancestry_required(False))
        self.assertFalse(lean.ancestry_required(True), "--offline makes it a warning")


class LsRemoteTests(unittest.TestCase):
    OUT = (f"{'1' * 40}\trefs/heads/dev\n{'2' * 40}\trefs/tags/v1\n{'3' * 40}\trefs/tags/v1^{{}}\n"
           f"{'4' * 40}\trefs/pull/7/head\n{'5' * 40}\trefs/tags/light\n")

    def run_ls_remote(self, ref, out=None):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            pats = cmd[3:]
            lines = [ln for ln in (self.OUT if out is None else out).splitlines()
                     if any(ln.split("\t")[1] == p or ln.split("\t")[1].endswith("/" + p) for p in pats)]
            return subprocess.CompletedProcess(cmd, 0, "".join(ln + "\n" for ln in lines), "")

        with mock.patch.object(lean.subprocess, "run", fake_run):
            return lean.ls_remote(TRU, ref), calls

    def test_branches_and_tags_only(self):
        sha, calls = self.run_ls_remote("dev")
        self.assertEqual(sha, "1" * 40)
        self.assertEqual(calls[0][:3], ["git", "ls-remote", UPSTREAM])
        self.assertEqual(calls[0][3:], ["refs/heads/dev", "refs/tags/dev", "refs/tags/dev^{}"])
        self.assertEqual(self.run_ls_remote("v1")[0], "3" * 40, "annotated tags are peeled to their commit")
        self.assertEqual(self.run_ls_remote("light")[0], "5" * 40)
        self.assertEqual(self.run_ls_remote("refs/heads/dev")[0], "1" * 40)
        with self.assertRaisesRegex(lean.LeanError, "no branch or tag of that name"):
            self.run_ls_remote("head")  # git ls-remote alone would match refs/pull/7/head by suffix
        with self.assertRaisesRegex(lean.LeanError, "no branch or tag of that name"):
            self.run_ls_remote("7/head")
        with self.assertRaisesRegex(lean.LeanError, "only branches"):
            self.run_ls_remote("refs/pull/7/head")
        with self.assertRaisesRegex(lean.LeanError, "full 40-character SHA"):
            self.run_ls_remote("8a24ea4e79de")
        self.assertEqual(self.run_ls_remote(COMMIT), (COMMIT, []), "a full SHA needs no network")


class PinBranchTests(unittest.TestCase):
    def setUp(self):
        self.repo = CoreRepo().__enter__()
        self.addCleanup(self.repo.__exit__, None, None, None)
        self.repo.book()
        make_lock().save()
        self.before = paths.LOCK_FILE.read_text(encoding="utf-8")
        os.environ.pop("GITHUB_ACTIONS", None)

    def use(self, ledger):
        patcher = mock.patch.object(lean, "Ledger", lambda r, **kw: ledger)
        patcher.start()
        self.addCleanup(patcher.stop)
        return ledger

    def test_off_branch_commit_is_refused(self):
        led = self.use(FakeLedger(on_branch=False))
        report = pin.pin(OLD_COMMIT, offline=True)
        self.assertFalse(report.written)
        self.assertIn(f"{OLD_COMMIT} is not on branch 'dev' of {TRU} (fake: not on branch)", report.refused)
        self.assertEqual(led.ancestry_calls, [(OLD_COMMIT, "dev")])
        self.assertEqual(led.calls, [], "nothing is resolved at a refused commit")
        self.assertEqual(paths.LOCK_FILE.read_text(encoding="utf-8"), self.before)
        self.assertIn("**Refused (lock not written):**", report.markdown())
        report = pin.pin(refresh=True, offline=True)
        self.assertTrue(report.refused, "--refresh re-verifies the locked commit too")
        from tbook import cli

        out = self.repo.root / "build" / "pin.md"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["pin", OLD_COMMIT, "--offline", "--report", str(out)]), 1)
        self.assertIn("Refused", out.read_text(encoding="utf-8"))
        self.assertEqual(paths.LOCK_FILE.read_text(encoding="utf-8"), self.before)

    def test_undetermined_ancestry(self):
        self.use(FakeLedger(on_branch=None))
        report = pin.pin(COMMIT, offline=False, dry_run=True)
        self.assertEqual(report.refused, "")
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("could not verify", report.warnings[0])
        self.assertIn("**Warnings:**", report.markdown())
        os.environ["GITHUB_ACTIONS"] = "true"
        report = pin.pin(COMMIT, offline=False, dry_run=True)
        self.assertIn("could not verify", report.refused, "in CI an unverifiable commit is refused")
        report = pin.pin(COMMIT, offline=True, dry_run=True)
        self.assertEqual((report.refused, len(report.warnings)), ("", 1), "--offline makes it a warning")

    def test_branch_head_and_other_refs(self):
        led = self.use(FakeLedger(on_branch=False))
        seen = []
        with mock.patch.object(lean, "ls_remote", lambda repo, ref: seen.append(ref) or COMMIT):
            report = pin.pin()
            self.assertEqual(seen, ["refs/heads/dev"])
            self.assertTrue(report.written, report.markdown())
            self.assertEqual(led.ancestry_calls, [], "the head of dev is on dev by construction")
            self.assertEqual(led.recorded, [(COMMIT, "dev")])
            self.assertEqual(lean.Lock.load().branch, "dev")
            pin.pin("dev", dry_run=True)
            self.assertEqual(seen[-1], "refs/heads/dev")
            report = pin.pin("feature-x")
            self.assertEqual(seen[-1], "feature-x")
            self.assertTrue(report.refused, "another branch's head must be on dev too")

    def test_abbreviated_sha(self):
        led = self.use(FakeLedger(shas={"aaaaaaaaaaaa": COMMIT}))
        report = pin.pin("aaaaaaaaaaaa", offline=True, dry_run=True)
        self.assertEqual(report.commit, COMMIT)
        self.assertEqual(led.ancestry_calls, [(COMMIT, "dev")])
        with self.assertRaisesRegex(lean.LeanError, "commit prefix the local trureturing checkout knows"):
            pin.pin("abcdef12", offline=True)
        unknown = lean.LeanError("no branch or tag; pass its full 40-character SHA")
        with mock.patch.object(lean, "ls_remote", side_effect=unknown):
            with self.assertRaisesRegex(lean.LeanError, "full 40-character SHA"):
                pin.pin("abcdef12")


class LedgerExpandShaTests(unittest.TestCase):
    def test_checkout_then_github(self):
        with CoreRepo():
            h = History()
            self.addCleanup(h.cleanup)
            gh = FakeGitHub({f"repos/{TRU}/commits/{COMMIT[:10]}": {"sha": COMMIT},
                             f"repos/{TRU}/commits/1234567": {"sha": "f" * 40}})
            with mock.patch.object(lean.urllib.request, "urlopen", gh):
                local = lean.Ledger(TRU, offline=True, checkout=h.dir)
                self.assertEqual(local.expand_sha(h.c[:12]), h.c)
                self.assertEqual(local.expand_sha(h.c[:12].upper()), h.c)
                self.assertIsNone(local.expand_sha("dev"), "only hex prefixes")
                self.assertIsNone(local.expand_sha(COMMIT[:10]), "offline: the checkout only")
                online = lean.Ledger(TRU)
                self.assertEqual(online.expand_sha(COMMIT[:10]), COMMIT)
                self.assertIsNone(online.expand_sha("1234567"), "an answer that does not extend the prefix")
                self.assertIsNone(online.expand_sha("7654321"), "unknown (404)")


class CheckBranchTests(unittest.TestCase):
    def run_lean(self, ledger, offline=False):
        with mock.patch.object(lean, "Ledger", lambda repo, **kw: ledger):
            issues: list[model.Issue] = []
            check.check_lean({"demo": model.load_book_models(config.load_book("demo"))}, make_lock(),
                             config.load_site(), issues, offline=offline)
            return issues

    def test_pinned_commit_must_be_on_the_branch(self):
        with CoreRepo() as repo:
            repo.book()
            os.environ.pop("GITHUB_ACTIONS", None)
            led = FakeLedger(on_branch=False)
            issues = self.run_lean(led)
            self.assertEqual([(i.severity, i.path) for i in issues], [("error", paths.LOCK_FILE)])
            self.assertIn(f"pinned commit {COMMIT[:12]} is not on branch 'dev' of {TRU} (fake: not on branch)",
                          issues[0].message)
            self.assertEqual(led.ancestry_calls, [(COMMIT, "dev")])
            self.assertEqual(self.run_lean(FakeLedger(on_branch=True)), [])
            issues = self.run_lean(FakeLedger(on_branch=None))
            self.assertEqual([i.severity for i in issues], ["warning"])
            self.assertIn("could not verify that pinned commit", issues[0].message)
            os.environ["GITHUB_ACTIONS"] = "true"
            self.assertEqual([i.severity for i in self.run_lean(FakeLedger(on_branch=None))], ["error"])
            self.assertEqual([i.severity for i in self.run_lean(FakeLedger(on_branch=None), offline=True)],
                             ["warning"], "--offline makes it a warning, even in CI")

    def test_committed_cache_is_an_error(self):
        with CoreRepo() as repo:
            check.check_cache(issues := [])
            self.assertEqual(issues, [], "not a git checkout")
            git(repo.root, "init", "-q")
            write(repo.root / ".cache/trureturing" / COMMIT / lean.ANCESTRY_FILE, "{}")
            check.check_cache(issues := [])
            self.assertEqual(issues, [], "untracked cache files are fine")
            git(repo.root, "add", "-f", ".cache")
            check.check_cache(issues := [])
            self.assertEqual([i.severity for i in issues], ["error"])
            self.assertIn("are committed", issues[0].message)


# --------------------------------------------------------------------------- finding 10: declaration lines


def located(source: str, name: str, module: str = "D5/S0/M") -> tuple[int, str]:
    res = lean.Resolution(gid="", module=module, name=name, kind="theorem", statement_id="")
    lean.locate(FakeLedger(sources={f"{module}.lean": textwrap.dedent(source)}), COMMIT, res)
    return res.line, res.signature


class LocateTests(unittest.TestCase):
    def test_qualified_names_inside_namespaces(self):
        src = """\
            namespace Lambda

            theorem LMonoTy.freeVars_of_subst_subset (S : Subst) : True := trivial

            theorem LMonoTys.freeVars_of_subst_subset (S : Subst) : True := trivial

            end Lambda
            """
        self.assertEqual(located(src, "Lambda.LMonoTys.freeVars_of_subst_subset"),
                         (5, "theorem LMonoTys.freeVars_of_subst_subset (S : Subst) : True"))
        self.assertEqual(located(src, "Lambda.LMonoTy.freeVars_of_subst_subset")[0], 3)

    def test_same_short_name_in_two_namespaces(self):
        src = """\
            /- namespace Decoy
            theorem foo : True := trivial -/
            namespace A
            -- theorem foo is below
            theorem foo : True := trivial
            end A

            noncomputable section
            namespace B
            @[simp]
            protected theorem foo : True := trivial
            theorem _root_.Top.foo : True := trivial
            end B
            end
            """
        self.assertEqual(located(src, "A.foo")[0], 5)
        self.assertEqual(located(src, "B.foo"), (10, "@[simp] protected theorem foo : True"))
        self.assertEqual(located(src, "Top.foo")[0], 12)
        self.assertEqual(located(src, "Decoy.foo")[0], 0, "comments are not declarations")
        self.assertEqual(located(src, "C.foo")[0], 0, "not written in this file: no guess")

    def test_unfollowable_scopes_fall_back_to_the_longest_unique_suffix(self):
        src = """\
            namespace X
            end Y
            theorem P.bar : True := trivial
            theorem Q.bar : True := trivial
            theorem baz : True := trivial
            private theorem qux : True := trivial
            """
        self.assertEqual(located(src, "Z.P.bar")[0], 3)
        self.assertEqual(located(src, "Z.R.bar")[0], 0, "two equally good candidates: line 0")
        self.assertEqual(located(src, "Z.baz")[0], 5)
        self.assertEqual(located(src, "Z.qux")[0], 0, "private declarations are never cited")

    def test_unicode_names_and_mutual_blocks(self):
        src = """\
            namespace FDRep
            mutual
            theorem even₂ : True := trivial
            theorem odd₂ : True := trivial
            end
            @[simp] theorem of_ρ_eq_self : True := trivial
            theorem «weird name» : True := trivial
            end FDRep
            """
        self.assertEqual(located(src, "FDRep.odd₂")[0], 4)
        self.assertEqual(located(src, "FDRep.of_ρ_eq_self")[0], 6)
        self.assertEqual(located(src, "FDRep.«weird name»")[0], 7)

    def test_pin_reports_moved_lines(self):
        with CoreRepo() as repo:
            repo.book()
            lean.Lock(repo=TRU, branch="dev", commit=COMMIT, pinned_at="2025-01-01T00:00:00Z",
                      declarations=lock_decls()).save()  # GID_3V at line 12
            src = "namespace D5.S1.Deficit\ntheorem deficit_three_valued : True := trivial\n"
            with mock.patch.object(lean, "Ledger", lambda r, **kw: FakeLedger(sources={f"{MOD_3V}.lean": src})):
                report = pin.pin(refresh=True, offline=True)
            self.assertIn((GID_3V, 12, 2), report.moved)
            self.assertIn(f"- `{GID_3V}`: L12 → L2", report.markdown())

    @unittest.skipUnless(REAL, f"needs a trureturing checkout ($TRURETURING_DIR) with {REAL_COMMIT[:12]}")
    def test_real_same_short_name(self):
        checkout, commit = REAL, REAL_COMMIT
        led = lean.Ledger(TRU, offline=True, checkout=checkout)
        res = lean.resolve(led, commit, "D5/S0/Rewriting/NativeSubstitution.LMonoTys.freeVars_of_subst_subset")
        lean.locate(led, commit, res)
        self.assertEqual(res.name, "Lambda.LMonoTys.freeVars_of_subst_subset")
        self.assertTrue(res.signature.startswith("theorem LMonoTys.freeVars_of_subst_subset"), res.signature)


# --------------------------------------------------------------------------- finding 11: GID syntax


class GidSyntaxTests(unittest.TestCase):
    def test_lean_identifiers(self):
        for name in ("of_ρ_eq_self", "FDRep.of_ρ_eq_self", "mk₂", "isSome?", "get!", "x'", "«a.b»",
                     "Foo.«with-dash».bar", "Gammaℝ", "αβ_γ", "xᵢ"):
            g = lean.parse_gid(f"D5/S3/M.{name}")
            self.assertEqual(g.name, name)
        self.assertEqual(lean.parse_gid("D5/S3/M.Foo.«a.b».c").parts, ["Foo", "a.b", "c"])
        for bad in ("D5/S3/M.«a b»", "D5/S3/M.«»", "D5/S3/M.a..b", "D5/S3/M.λx", "D5/S3/M.1b", "D5/S3/M.a-b",
                    "D5/S3/M.«a", "D5/S3/M.a.", "D5/S3/M.«a,b»"):
            with self.assertRaises(lean.LeanError, msg=bad):
                lean.parse_gid(bad)

    def test_name_to_str_escapes_only_non_identifiers(self):
        self.assertEqual(lean.name_to_str(["FDRep", "of_ρ_eq_self", "mk₂"]), "FDRep.of_ρ_eq_self.mk₂")
        self.assertEqual(lean.name_to_str(["a-b", "λx", "Π"]), "«a-b».«λx».«Π»")
        self.assertTrue(lean.is_identifier("Sᵥₙ_nonneg"))
        self.assertFalse(lean.is_identifier("₂x"))

    def test_resolve_matches_components(self):
        st = {"statement_id": "s", "declarations": [
            {"declaration_name_key": name_key("D5", "S3", "FDRep", "of_ρ_eq_self"), "kind": "theorem"},
            {"declaration_name_key": name_key("X", "a.b"), "kind": "theorem"},
            {"declaration_name_key": name_key("X", "b"), "kind": "def"}]}
        led = FakeLedger({"D5/S3/M": st})
        for gid in ("D5/S3/M.of_ρ_eq_self", "D5/S3/M.FDRep.«of_ρ_eq_self»", "D5/S3/M.D5.S3.FDRep.of_ρ_eq_self"):
            self.assertEqual(lean.resolve(led, COMMIT, gid).name, "D5.S3.FDRep.of_ρ_eq_self", gid)
        self.assertEqual(lean.resolve(led, COMMIT, "D5/S3/M.«a.b»").name, "X.«a.b»")
        self.assertEqual(lean.resolve(led, COMMIT, "D5/S3/M.b").kind, "def", "b is not a suffix of «a.b»")

    @unittest.skipUnless(REAL, f"needs a trureturing checkout ($TRURETURING_DIR) with {REAL_COMMIT[:12]}")
    def test_real_blueprint_gid(self):
        checkout, commit = REAL, REAL_COMMIT
        led = lean.Ledger(TRU, offline=True, checkout=checkout)
        res = lean.resolve(led, commit, "D5/S3/FiniteGroups/FiniteCharacterAlgebra.of_ρ_eq_self")
        self.assertEqual((res.kind, res.name),
                         ("theorem", "D5.S3.FiniteGroups.FiniteCharacterAlgebra.FDRep.of_ρ_eq_self"))


# --------------------------------------------------------------------------- findings 27, 35: pin report


class PinReportTests(unittest.TestCase):
    def setUp(self):
        self.repo = CoreRepo().__enter__()
        self.addCleanup(self.repo.__exit__, None, None, None)
        self.repo.book()
        patcher = mock.patch.object(lean, "Ledger", lambda r, **kw: FakeLedger())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_directory_is_created(self):
        from tbook import cli

        make_lock().save()
        out = self.repo.root / "build" / "deeper" / "pin.md"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["pin", "--refresh", "--offline", "--report", str(out)]), 0)
        self.assertIn("trureturing pin:", out.read_text(encoding="utf-8"))

    def test_unwritable_report_leaves_the_lock_alone(self):
        from tbook import cli

        lean.Lock(repo=TRU, branch="dev", commit=COMMIT, pinned_at="2025-01-01T00:00:00Z", declarations={}).save()
        before = paths.LOCK_FILE.read_text(encoding="utf-8")
        write(self.repo.root / "build", "a file, not a directory")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            report = str(self.repo.root / "build" / "x" / "pin.md")
            self.assertEqual(cli.main(["pin", "--refresh", "--offline", "--report", report]), 1)
        self.assertIn("cannot write --report", err.getvalue())
        self.assertEqual(paths.LOCK_FILE.read_text(encoding="utf-8"), before)

    def test_unresolved_cited_gid_is_not_removed(self):
        stale = "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued_old"
        for lang in ("zh", "en"):
            p = config.load_book("demo").edition(lang).dir / "ch02.md"
            p.write_text(p.read_text(encoding="utf-8") + f'\n::: {{.lemma #lem-old lean="{stale}"}}\nx\n:::\n',
                         encoding="utf-8")
        gone = {"module": "D5/S1/Old/Gone", "name": "x", "kind": "theorem"}
        make_lock(lock_decls(**{stale: dict(lock_decls()[GID_3V], name="D5.S1.Deficit.deficit_three_valued_old"),
                                "D5/S1/Old/Gone.x": gone})).save()
        report = pin.pin(refresh=True, offline=True, dry_run=True)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("deficit_three_valued_old", report.errors[0])
        self.assertEqual(report.removed, ["D5/S1/Old/Gone.x"], "still cited, so not removed")
        text = report.markdown()
        self.assertEqual(text.count("deficit_three_valued_old"), 2, text)  # the error line names it twice


# --------------------------------------------------------------------------- finding 29: SUMMARY parity


class SummaryParityTests(unittest.TestCase):
    def parity(self, en_summary: str) -> list[model.Issue]:
        with CoreRepo() as repo:
            book = repo.book(summaries={"zh": ZH_SUMMARY, "en": en_summary})
            issues: list[model.Issue] = []
            check.check_parity(book, model.load_book_models(book), issues)
            return issues

    def test_same_structure_passes(self):
        self.assertEqual(self.parity(EN_SUMMARY), [])

    def test_nesting_numbering_and_sections_must_agree(self):
        nested = EN_SUMMARY.replace("- [Chapter 2](ch02.md)", "  - [Chapter 2](ch02.md)").replace(
            "  - [Section 2.1]", "    - [Section 2.1]")
        msgs = messages(self.parity(nested))
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn("ch02.md is numbered chapter 1.1, nested at depth 1 (theorems 1.n) in the en edition but "
                      "numbered chapter 2 (theorems 2.n) in the zh edition", msgs[0])
        draft = EN_SUMMARY.replace("- [Chapter 1](ch01.md)", "- [Chapter 1](ch01.md)\n- [Draft]()")
        self.assertIn("ch02.md is numbered chapter 3", messages(self.parity(draft))[0])
        prefix = EN_SUMMARY.replace("[Preface](README.md)\n", "").replace(
            "- [Chapter 1](ch01.md)", "- [Preface](README.md)\n- [Chapter 1](ch01.md)")
        msgs = messages(self.parity(prefix))
        self.assertIn("README.md is numbered chapter 1 (theorems 1.n) in the en edition but a prefix chapter", msgs[0])
        suffix = EN_SUMMARY.replace("[Appendix A](appendix-a.md)\n", "").replace(
            "- [Draft]()", "- [Draft]()\n- [Appendix A](appendix-a.md)")
        self.assertIn("appendix-a.md is numbered chapter 4", messages(self.parity(suffix))[0])


# --------------------------------------------------------------------------- findings 32, 34: lock checks


class LockCheckTests(unittest.TestCase):
    def test_book_filter_counts_other_books_citations(self):
        with CoreRepo() as repo:
            demo = repo.book()
            second = repo.book("second", langs=("zh",), summaries={"zh": "- [A](a.md)\n"}, files={"zh": {
                "a.md": f'::: {{.theorem #thm-only lean="{GID_INT}"}}\nx\n:::\n'}})
            extra = {"D5/S1/Old/Gone.x": {"module": "D5/S1/Old/Gone", "name": "x", "kind": "theorem"}}
            make_lock(dict(lock_decls(), **extra)).save()
            with mock.patch.object(lean, "Ledger", lambda r, **kw: FakeLedger()), \
                    mock.patch.object(check.importlib, "import_module", side_effect=media_stub):
                unused = [m for m in messages(check.run([second], offline=True)) if "no longer cited" in m]
                self.assertEqual(unused, ["D5/S1/Old/Gone.x is locked but no longer cited; ./tbook pin --refresh "
                                          "prunes it"], "demo's citations are still cited")
                unused = [m for m in messages(check.run([demo, second], offline=True)) if "no longer cited" in m]
                self.assertEqual(len(unused), 1)
                write(repo.root / "books" / "broken" / "book.toml", "not toml [")
                unused = [m for m in messages(check.run([second], offline=True)) if "no longer cited" in m]
                self.assertEqual(unused, [], "other books unreadable: the warning is skipped, not guessed")

    def test_kind_error_at_each_theorem_like_environment(self):
        with CoreRepo() as repo:
            book = repo.book()
            for lang in ("zh", "en"):
                p = book.edition(lang).dir / "ch02.md"
                p.write_text(p.read_text(encoding="utf-8") + f'\n::: {{.theorem #thm-def lean="{GID_DEF}"}}\nx\n:::\n',
                             encoding="utf-8")
            slide = repo.root / "books" / "demo" / "slides" / "deck" / "slides.md"
            with mock.patch.object(lean, "Ledger", lambda r, **kw: FakeLedger()):
                issues: list[model.Issue] = []
                check.check_lean({"demo": model.load_book_models(config.load_book("demo"))}, make_lock(),
                                 config.load_site(), issues, offline=True, extra_cited=[(slide, 44, GID_DEF)])
            kind = [(i.path.relative_to(repo.root).as_posix(), i.line)
                    for i in issues if "must cite theorems" in i.message]
            self.assertEqual(kind, [("books/demo/zh/ch02.md", 9), ("books/demo/en/ch02.md", 9)])


if __name__ == "__main__":
    unittest.main()
