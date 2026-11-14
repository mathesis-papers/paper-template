"""Structural layout fixtures contain no mathematical statements or receipts."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('layout_paper', ROOT / 'docs/layer-mathesis/scripts/paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mathesis-layout-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.put('template.toml', '[template]\nname="fixture"\nrepo="fixture/template"\nversion="0.8.2"\n'
                 '[managed]\npaths=["tools/", "docs/", ".gitignore", "template.toml", "template-manifest.json"]\n'
                 'exclude=["docs/layer-", "docs/project/"]\nowned=["books/"]\n')
        self.put('template.d/mathesis.toml', '[template]\nname="mathesis"\nrepo="mathesis-papers/paper-template"\nversion="0.5.0"\n'
                 '[managed]\npaths=["docs/layer-mathesis/"]\n')
        self.put('.gitignore', 'build/\n.cache/\n__pycache__/\nnode_modules/\n')
        self.put('tools/evidence.py', '# Reusable managed source, not a run record.\n')
        self.put('docs/guide.md', '# Managed source\n')
        self.put('template.d/mathesis.manifest.json', json.dumps({'files': {}}))
        self.json('template-manifest.json', {'files': {n: {'sha256': paper.digest(self.root / n), 'mode': '100644'}
                  for n in ('template.toml', '.gitignore', 'tools/evidence.py', 'docs/guide.md')}})
        self.slug = 'layout-fixture'
        self.json('paper.json', {'work': {'work': self.slug}})
        self.mapping = {'book': self.slug, 'work': self.slug, 'version': 1, 'stage': 'skeleton',
                        'results': {}, 'pending_claims': []}
        self.json('.mathesis/book.json', self.mapping)
        self.put('site.toml', '[site]\nbase_url="https://example.invalid/paper/"\n')
        self.put('README.md', '# Structural fixture\n')
        for name in ('CITATION.cff', 'paper.pdf', 'formalization/nodes.json', 'LICENSES/CC-BY-4.0.txt',
                     'manuscript/source.tex', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', 'PROJECT.md', 'trureturing.lock.json'):
            self.put(name, 'structural fixture\n')
        self.put(f'books/{self.slug}/book.toml', '[book]\n')
        for lang in ('zh', 'en'):
            self.put(f'books/{self.slug}/{lang}/README.md', '# Structural fixture\n')
        for name in paper.layout_rules()['empty_media']:
            self.put(f'books/{self.slug}/{name}/.gitkeep', '')
        generated = ['paper.json', 'CITATION.cff', 'paper.pdf', 'formalization/nodes.json', 'LICENSES/CC-BY-4.0.txt',
                     'manuscript/source.tex', 'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md']
        self.json('.mathesis/generated.json', {'generated_paths': generated,
                  'sha256': {n: paper.digest(self.root / n) for n in generated}})
        self.quiet(paper.front, self.root)

    def quiet(self, fn, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args, **kwargs)

    def put(self, name, text='fixture\n'):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def json(self, name, data):
        return self.put(name, json.dumps(data))

    def issues(self):
        return '\n'.join(f'{n}: {rule}' for n, rule in paper.layout_issues(self.root))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}

    def test_clean_tree_and_reusable_sources(self):
        self.assertEqual(self.issues(), '')
        self.put(f'books/{self.slug}/figures/diagram.py', '# reusable figure generator\n')
        self.put(f'books/{self.slug}/figures/diagram.zh.svg', '<svg/>')
        self.assertEqual(self.issues(), '')

    def test_unknown_root_file_and_empty_directory(self):
        for name in ('random.txt', 'unexpected'):
            with self.subTest(name=name):
                p = self.put(name) if '.' in name else self.root / name
                if not p.exists(): p.mkdir()
                self.assertIn(name + ': four zones: unknown root entry', self.issues())
                p.unlink() if p.is_file() else p.rmdir()

    def test_examples_extra_books_and_missing_book(self):
        for name in ('example-monograph', 'another-paper'):
            p = self.put(f'books/{name}/book.toml')
            self.assertIn('zone 2 requires exactly one book', self.issues())
            self.assertIn(str(p.relative_to(self.root)), self.issues())
            shutil.rmtree(p.parent)
        shutil.rmtree(self.root / 'books' / self.slug)
        self.assertIn('zone 2 requires exactly one book', self.issues())
        self.assertIn('requires the bilingual content skeleton', self.issues())

    def test_slug_short_form_requires_documentation(self):
        p = self.root / 'books' / self.slug
        p.rename(p.with_name('short'))
        self.mapping['book'] = 'short'
        self.json('.mathesis/book.json', self.mapping)
        self.assertIn('short_slug_reason', self.issues())
        self.mapping['short_slug_reason'] = 'Documented short form of layout-fixture.'
        self.json('.mathesis/book.json', self.mapping)
        self.quiet(paper.front, self.root)
        self.assertEqual(self.issues(), '')

    def test_content_entries_and_one_off_scripts(self):
        for name in ('unknown-media/asset.json', 'misc.txt', 'en/work.py'):
            p = self.put(f'books/{self.slug}/{name}')
            self.assertIn('zone 2', self.issues())
            p.unlink()
            if name.startswith('unknown-media/'): p.parent.rmdir()

    def test_every_skeleton_entry_is_required_with_its_expected_type(self):
        for name in paper.layout_rules()['content']:
            p = self.root / 'books' / self.slug / name
            saved = p.with_name(name + '.saved')
            p.rename(saved)
            with self.subTest(name=name):
                self.assertIn(str(p.relative_to(self.root)) + ': zone 2 requires the bilingual content skeleton', self.issues())
            saved.rename(p)

    def test_every_debris_directory_and_pattern(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        rules = paper.layout_rules()
        for directory in rules['forbidden_directories']:
            name = directory + '/result.txt' if '/' in directory else f'books/{self.slug}/assets/{directory}/result.txt'
            with self.subTest(name=name):
                p = self.put(name)
                subprocess.run(['git', '-C', str(self.root), 'add', '-f', name], check=True)
                self.assertIn('preparation debris/run records', self.issues())
                subprocess.run(['git', '-C', str(self.root), 'rm', '--cached', '-q', '--', name], check=True)
                shutil.rmtree(p.parent)
        for pattern in rules['forbidden_filenames']:
            name = f'books/{self.slug}/assets/' + pattern.replace('*', 'sample')
            with self.subTest(pattern=pattern):
                p = self.put(name)
                self.assertIn('preparation debris/run records', self.issues())
                p.unlink()

    def test_every_built_suffix_and_size_limit(self):
        for suffix in paper.layout_rules()['built_suffixes']:
            with self.subTest(suffix=suffix):
                p = self.put(f'books/{self.slug}/assets/rendered{suffix}')
                self.assertIn('built output', self.issues())
                p.unlink()
        p = self.root / 'books' / self.slug / 'assets' / 'large.png'
        with p.open('wb') as stream: stream.truncate(2097152)
        self.assertEqual(self.issues(), '')
        with p.open('ab') as stream: stream.write(b'!')
        self.assertIn('exceeds 2 MiB', self.issues())
        p.unlink()
        for name in ('paper.pdf', 'manuscript/source.tex'):
            p = self.root / name
            with p.open('wb') as stream: stream.truncate(2097153)
            manifest = paper.read_json(self.root / '.mathesis/generated.json')
            manifest['sha256'][name] = paper.digest(p)
            self.json('.mathesis/generated.json', manifest)
        self.assertEqual(self.issues(), '')

    def test_generated_ownership_and_manifest_cannot_claim_other_zones(self):
        self.put('paper.pdf', 'tampered')
        self.assertIn('paper.pdf: zone 1 generated hash mismatch', self.issues())
        for name in ('LICENSES/extra.txt', 'manuscript/extra.tex', 'formalization/extra.json', '.mathesis/extra.json'):
            p = self.put(name)
            self.assertIn(name + ': zone 1', self.issues())
            p.unlink()
        manifest = paper.read_json(self.root / '.mathesis/generated.json')
        for name in (f'books/{self.slug}/en/README.md', 'tools/evidence.py', 'rogue.txt'):
            manifest['sha256'][name] = '0' * 64
            self.json('.mathesis/generated.json', manifest)
            self.assertIn(name + ': zone 1 generated manifest cannot claim', self.issues())

    def test_manifest_requires_complete_unique_generated_path_inventory(self):
        path = self.root / '.mathesis/generated.json'
        original = paper.read_json(path)
        for name in paper.REQUIRED | set(paper.layout_rules()['catalog_front']):
            manifest = json.loads(json.dumps(original))
            del manifest['sha256'][name]
            self.json('.mathesis/generated.json', manifest)
            self.assertIn(name + ': zone 1 required publisher file', self.issues())
            self.assertIn('generated paths/hash keys differ', self.issues())
        manifest = json.loads(json.dumps(original))
        manifest['generated_paths'].append('paper.json')
        self.json('.mathesis/generated.json', manifest)
        self.assertIn('generated paths/hash keys differ or are duplicated', self.issues())

    def test_front_prefix_and_generated_guide_are_both_checked(self):
        original = (self.root / 'README.md').read_bytes()
        (self.root / 'README.md').write_bytes(original + b'unsanctioned suffix')
        self.assertIn('zone 4 generated repository guide differs', self.issues())
        self.quiet(paper.front, self.root)
        self.assertEqual((self.root / 'README.md').read_bytes(), original)
        (self.root / 'README.md').write_bytes(original.replace(b'Structural fixture', b'changed prefix'))
        self.assertIn('zone 1 generated hash mismatch', self.issues())
        with self.assertRaisesRegex(ValueError, 'publisher repair'):
            self.quiet(paper.front, self.root)

    def test_machinery_and_template_metadata_allowlists(self):
        for name, expected in [('docs/local.md', 'zone 3'), ('tools/one-off.py', 'zone 3'),
                               ('template.d/notes.md', 'zone 4')]:
            p = self.put(name)
            self.assertIn(name + ': ' + expected, self.issues())
            p.unlink()

    def test_single_review_and_consistent_statement_rows(self):
        row = {'claim': 'structural-only', 'gids': [], 'comparison_verdict': 'none',
               'compared_public_gid': None, 'comparison_commit': 'a' * 40}
        self.mapping['results'] = {'fixture-result': row}
        self.json('.mathesis/book.json', self.mapping)
        self.quiet(paper.front, self.root)
        self.assertIn('requires a statement comparison', self.issues())
        self.json('.mathesis/review.json', {'results': {'fixture-result': dict(row, scope='Structural comparison fixture.')}})
        self.quiet(paper.front, self.root)
        self.assertEqual(self.issues(), '')
        p = self.put('.mathesis/REVIEW.md', '| fixture-result | none | — | ' + 'a'*40 + ' | Structural fixture. |\n')
        self.assertIn('only one statement review', self.issues())
        (self.root / '.mathesis/review.json').unlink()
        self.quiet(paper.front, self.root)
        self.assertEqual(self.issues(), '')
        for text in ('', p.read_text().replace('none', 'same'), p.read_text().replace('a'*40, 'b'*40),
                     p.read_text().replace('—', 'unrelated.declaration')):
            original = p.read_text()
            p.write_text(text)
            self.assertIn('zone 1 statement review', self.issues())
            p.write_text(original)

    def test_symlinks_cannot_escape_record_content_or_front(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        for name in (f'books/{self.slug}/assets/link', '.mathesis/link', 'front-link'):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.symlink_to(outside, target_is_directory=True)
            self.assertIn(name + ': zones 1–2 and 4 require real', self.issues())
            p.unlink()

    def test_ignored_local_work_is_allowed_but_tracked_output_is_rejected(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.put('build/rendered.pdf')
        self.put('.cache/local.log')
        self.assertEqual(self.issues(), '')
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', 'build/rendered.pdf'], check=True)
        self.assertIn('build/rendered.pdf: all zones: built output', self.issues())
        self.assertIn('build: four zones: unknown root', self.issues())

    def test_tidy_dry_run_apply_idempotence_and_protected_zones(self):
        self.put('docs/project/validation/old.log')
        self.put('books/example-monograph/en/README.md')
        self.put('unknown/file.txt')
        self.put('.mathesis/protected.log')
        self.put('formalization/protected.json')
        self.put(f'books/{self.slug}/assets/protected.log')
        self.put('books/other-paper/en/README.md')
        self.put('paper.pdf', 'tampered publisher bytes')
        before = self.snapshot()
        moves, protected = self.quiet(paper.tidy, self.root)
        self.assertEqual(self.snapshot(), before)
        archive = Path(self.tmp.name) / 'external-archive'
        applied, _ = self.quiet(paper.tidy, self.root, apply=True, archive=archive)
        self.assertEqual(set(moves), set(applied))
        self.assertTrue((archive / 'docs/project/validation/old.log').is_file())
        self.assertTrue((archive / 'books/example-monograph/en/README.md').is_file())
        for name, data in before.items():
            if name.startswith(('.mathesis/', 'formalization/', f'books/{self.slug}/', 'books/other-paper/')) or name == 'paper.pdf':
                self.assertEqual((self.root / name).read_bytes(), data, name)
        self.assertTrue(protected)
        self.assertEqual(self.quiet(paper.tidy, self.root, apply=True)[0], [])
        with self.assertRaisesRegex(ValueError, 'outside'):
            self.quiet(paper.tidy, self.root, archive=self.root / 'bad-archive')

    def test_unfilled_template_has_no_examples(self):
        for name in ('paper.json', 'CITATION.cff', 'paper.pdf', 'formalization', 'manuscript', 'LICENSES', '.mathesis', 'books'):
            p = self.root / name
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        self.quiet(paper.front, self.root)
        self.assertEqual(self.issues(), '')
        self.put('books/example-monograph/book.toml')
        self.assertIn('zero books in an unfilled template', self.issues())

    def test_real_template_update_does_not_restore_deleted_examples(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        from tbook import template
        (self.root / 'template-manifest.json').write_text(
            template.build_manifest(self.root, template.TemplateConfig.load(self.root)).to_json())
        source = Path(self.tmp.name) / 'upstream'
        source.mkdir()
        config = self.root / 'template.toml'
        (source / 'template.toml').write_text(config.read_text().replace('0.8.2', '0.8.3'))
        shutil.copytree(self.root / 'tools', source / 'tools')
        shutil.copytree(self.root / 'docs', source / 'docs')
        shutil.copyfile(self.root / '.gitignore', source / '.gitignore')
        example = source / 'books/example-monograph/book.toml'
        example.parent.mkdir(parents=True)
        example.write_text('upstream example fixture\n')
        cfg = template.TemplateConfig.load(source)
        (source / 'template-manifest.json').write_text(template.build_manifest(source, cfg).to_json())
        result = template.update(self.root, layer=None, source=str(source))
        self.assertFalse(result.errors, result.errors)
        self.assertFalse((self.root / 'books/example-monograph').exists())
        self.assertTrue((self.root / 'books' / self.slug / 'en/README.md').is_file())

    def test_migration_preserves_record_and_content_and_is_idempotent(self):
        self.put('docs/project/HANDOFF.md')
        migration_spec = importlib.util.spec_from_file_location('layout_migration', ROOT / 'docs/layer-mathesis/migrations/v0.5.0.py')
        migration = importlib.util.module_from_spec(migration_spec)
        migration_spec.loader.exec_module(migration)
        target = self.root / 'docs/layer-mathesis'
        shutil.copytree(ROOT / 'docs/layer-mathesis', target, ignore=shutil.ignore_patterns('__pycache__'))
        # These fixture machinery files are not part of the minimal manifest;
        # preview may report them, but cannot mutate them or the paper zones.
        before = self.snapshot()
        self.quiet(migration.migrate, self.root)
        self.assertEqual(self.snapshot(), before)
        self.quiet(migration.migrate, self.root)
        self.assertEqual(self.snapshot(), before)
