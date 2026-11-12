"""Written proofs stay distinct from both kernel verification and open problems."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile
from types import SimpleNamespace

from tbook import check, config, ledger, model, render, slides, site, pandoc as tp
from test_pandoc import have_pandoc, have_typst, run_filters
from test_core import CoreRepo, GID_3V, make_lock, write


class WrittenProofTests(unittest.TestCase):
    def book(self, repo, attrs='status="written-proof" proof="pf-a"', proof='A written argument.'):
        book = repo.book()
        for lang in book.languages:
            write(book.edition(lang).dir / 'ch01.md', f'''# Statement

::: {{.theorem #thm-a {attrs}}}
The statement from the source.
:::
''')
            # A proof may be in another chapter; adjacency is not evidence of association.
            write(book.edition(lang).dir / 'ch02.md', f'''# Argument

::: {{.proof #pf-a}}
{proof}
:::
''')
        return book

    def test_proof_in_each_edition_and_parity(self):
        with CoreRepo() as repo:
            book = self.book(repo)
            models = model.load_book_models(book)
            issues = []
            for edition in models.values():
                check.check_env_policy(edition, issues)
            check.check_parity(book, models, issues)
            self.assertEqual(issues, [])
            path = book.edition('en').dir / 'ch02.md'
            path.write_text('# No argument\n')
            issues = []
            check.check_env_policy(model.load_edition(book.edition('en')), issues)
            self.assertTrue(any('naming a proof block' in i.message for i in issues))

    def test_invalid_status_proof_and_lean_combinations(self):
        cases = [
            ('status="written-proof"', 'argument', 'needs proof='),
            ('status="written-proof" proof="thm-a"', 'argument', 'naming a proof block'),
            ('status="written-proof" proof="pf-a"', '<!-- hidden -->', 'is empty'),
            ('status="written-proof" proof="pf-a" lean=""', 'argument', 'must not also have lean'),
            (f'status="written-proof" proof="pf-a" lean="{GID_3V}"', 'argument', 'must not also have lean'),
            ('status="written-proff"', 'argument', 'unknown result status'),
        ]
        for attrs, proof, message in cases:
            with self.subTest(attrs=attrs, proof=proof), CoreRepo() as repo:
                book = self.book(repo, attrs, proof)
                issues = []
                check.check_env_policy(model.load_edition(book.edition('en')), issues)
                self.assertTrue(any(message in i.message for i in issues), issues)

    def test_open_and_non_result_cannot_claim_written_proof(self):
        for kind in (*model.OPEN, 'definition', 'remark', 'proof'):
            with self.subTest(kind=kind), CoreRepo() as repo:
                book = self.book(repo)
                path = book.edition('en').dir / 'ch01.md'
                path.write_text(path.read_text().replace('.theorem', '.' + kind))
                issues = []
                check.check_env_policy(model.load_edition(book.edition('en')), issues)
                self.assertTrue(any('only for theorem/' in i.message for i in issues))

    def test_language_status_and_proof_target_must_match(self):
        for replacement in ('status="written-proof"', 'proof="pf-other"'):
            with self.subTest(replacement=replacement), CoreRepo() as repo:
                book = self.book(repo)
                path = book.edition('en').dir / 'ch01.md'
                text = path.read_text()
                text = text.replace(replacement, '') if replacement.startswith('status') else text.replace('proof="pf-a"', replacement)
                path.write_text(text)
                issues = []
                check.check_parity(book, model.load_book_models(book), issues)
                self.assertTrue(any('differs between editions' in i.message for i in issues))

    def test_render_and_ledger_never_imply_lean_even_with_invalid_gid(self):
        for invalid_gid in ('', f' lean="{GID_3V}"'):
            with CoreRepo() as repo:
                book = self.book(repo, 'status="written-proof" proof="pf-a"' + invalid_gid)
                for lang, label in [('en', 'WRITTEN PROOF'), ('zh', '书面证明')]:
                    ed = book.edition(lang)
                    m = model.load_edition(ed)
                    env = m.envs['thm-a']
                    ctx = render.RenderContext(config.load_site(), book, ed, m, make_lock(), target='mdbook')
                    v = render.env_view(env, ctx)
                    self.assertEqual(v['badge'], label)
                    self.assertEqual(v['status'], 'written-proof')
                    self.assertEqual(v['badge_url'], '')
                    self.assertEqual(v['lean'], [])
                    self.assertFalse(render.env_verified(env, make_lock()))
                    self.assertNotIn(env, render.verified_envs(m.all_envs(), make_lock()))
                    html = render.mdbook_env(env, v, 'statement')
                    self.assertIn('tr-badge-written-proof', html)
                    self.assertNotIn('<a ', html)
                    pandoc = render.pandoc_env(env, v, 'statement')
                    self.assertIn('tr-status="written-proof"', pandoc)
                    self.assertNotIn('tr-badge-url=', pandoc)
                    self.assertNotIn('tr-lean=', pandoc)
                    text = ledger.ledger_markdown(m, make_lock())
                    written = text.split(config.s(lang, 'ledger.written_title'), 1)[1].split(config.s(lang, 'ledger.open_title'), 1)[0]
                    self.assertIn('#thm-a', written)
                    self.assertIn('#pf-a', written)
                    self.assertNotIn(GID_3V, written)

    def test_site_summary_keeps_written_proof_out_of_unverified_group(self):
        with CoreRepo() as repo:
            book = self.book(repo)
            m = model.load_edition(book.edition('en'))
            view = SimpleNamespace(models={'en': m}, lock=make_lock(), built={}, bdir=repo.root)
            html = site.verification_html(view, 'en', 'en')
            self.assertIn('WRITTEN PROOF', html)
            self.assertNotIn('UNVERIFIED', html)
            self.assertIn('vlist written-proof', html)

    def test_slide_status_and_book_citation(self):
        with CoreRepo() as repo:
            book = self.book(repo)
            m = model.load_edition(book.edition('en'))
            ed, slide = SimpleNamespace(path=book.edition('en').dir / 'slides.md', lang='en'), SimpleNamespace(line=1)
            errors = []
            err = lambda *args: errors.append(args[-1])
            citation = SimpleNamespace(tag='TheoremCard', gid='', attrs={'status':'written-proof', 'cite':'thm-a', 'label':m.envs['thm-a'].ref_text('en')})
            slides._check_citation(citation, ed, slide, make_lock(), err)
            slides._check_cite(citation, ed, slide, m, err)
            self.assertEqual(errors, [])
            citation.attrs['gid'] = ''
            slides._check_citation(citation, ed, slide, make_lock(), err)
            self.assertTrue(any('must not have gid' in e for e in errors))
            errors.clear()
            citation.attrs.pop('gid')
            citation.attrs['status'] = 'argued'
            slides._check_cite(citation, ed, slide, m, err)
            self.assertTrue(any('written-proof status must agree' in e for e in errors))


# Real Pandoc/Lua/Typst conversions catch divergence hidden by intermediate Markdown.


@unittest.skipUnless(have_pandoc(), 'Pandoc is required')
class WrittenProofOutputTests(unittest.TestCase):
    def test_lua_html_and_typst_preserve_written_status(self):
        with CoreRepo() as repo:
            book = WrittenProofTests().book(repo)
            ed = book.edition('en')
            m = model.load_edition(ed)
            ctx = render.RenderContext(config.load_site(), book, ed, m, make_lock(), target='pandoc')
            md = render.chapter_markdown(m.chapters[1], ctx)
            html = run_filters(md, 'html5')
            self.assertIn('tr-status-written-proof', html)
            self.assertIn('tr-badge-written-proof', html)
            self.assertIn('WRITTEN PROOF', html)
            self.assertNotIn('<a ', html)
            typ = run_filters(md, 'typst')
            self.assertIn('status: "written-proof"', typ)
            self.assertIn('badge: "WRITTEN PROOF"', typ)
            self.assertIn('badge-url: ""', typ)

    @unittest.skipUnless(have_typst(), 'Typst is required')
    def test_all_pdf_variants_and_epub_build_with_written_proof(self):
        with CoreRepo() as repo, tempfile.TemporaryDirectory(prefix='tbook-written-outputs-') as tmp:
            book = WrittenProofTests().book(repo)
            ed = book.edition('en')
            m = model.load_edition(ed)
            out = Path(tmp)
            for variant in config.PDF_VARIANTS:
                pdf = tp.build_pdf(config.load_site(), book, ed, m, make_lock(), variant,
                                   out / (variant + '.pdf'), stage_dir=out / variant)
                self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
                src = (out / variant / 'main.typ').read_text()
                self.assertIn('status: "written-proof"', src)
                self.assertIn('badge: "WRITTEN PROOF"', src)
            with mock.patch.dict('os.environ', {'TBOOK_EPUBCHECK': '0'}):
                epub = tp.build_epub(config.load_site(), book, ed, m, make_lock(), out / 'book.epub',
                                     stage_dir=out / 'epub')
            with zipfile.ZipFile(epub) as z:
                xhtml = '\n'.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xhtml'))
                self.assertIn('tr-badge-written-proof', xhtml)
                self.assertIn('WRITTEN PROOF', xhtml)
                self.assertRegex(xhtml, r'<span[^>]*tr-badge-written-proof[^>]*>WRITTEN PROOF</span>')
