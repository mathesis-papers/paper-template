"""Reader copy adaptation keeps the original player and exact source links."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("media_pages", ROOT / "docs/layer-mathesis/scripts/media_pages.py")
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)

PAGE = '''<!doctype html><html lang="zh" data-title-zh="INTERNAL//CODE" data-title-en="INTERNAL//CODE">
<head><meta name="generator" content="tbook film"><title>INTERNAL//CODE</title>
<script src="assets/films.js"></script></head><body><header>
<h1 class="logo">INTERNAL<b>//</b>CODE</h1><div class="tagline">Internal code</div>
<nav class="status"><span class="pill">FILMS 1</span><a class="pill" href="pinned-tree">PIN</a>
<button data-lang-set="en" aria-pressed="false">EN</button></nav></header>
<section class="hero panel"><h2>Canvas implementation</h2><p>How we render</p></section>
<article id="001-demo"><video controls poster="001-demo/poster.jpg"><source src="001-demo/narrated.mp4" type="video/mp4"></video>
<p class="kicker">Film 001 · <span class="dur">2:45</span> · Released yesterday</p>
<h3>A mathematical explanation</h3><p class="sum">The story itself, including the words AI narration when relevant.</p>
<p class="meta"><span>English AI narration</span></p>
<div class="lean"><h4>Frozen sources</h4><ul><li><a href="https://github.com/project/proof/blob/pinned/Theorem.lean#L37"><code>Exact.result</code></a></li></ul></div>
<a href="001-demo/narrated.mp4" download>720p</a></article>
<footer class="foot"><span>./tbook film new and build paths</span><span>upstream books</span></footer>
</body></html>'''
WORK = {"authors": [{"name": "First & Co"}, {"name": "Second"}], "license": "CC-BY-4.0"}


class MediaPages(unittest.TestCase):
    def test_reader_copy_preserves_player_language_evidence_and_download(self):
        updated = media.adapt_film_page(PAGE, WORK)
        for literal in ('<video controls poster="001-demo/poster.jpg">',
                        '<source src="001-demo/narrated.mp4" type="video/mp4">',
                        '<button data-lang-set="en" aria-pressed="false">EN</button>',
                        'href="001-demo/narrated.mp4" download', 'id="001-demo"',
                        'https://github.com/project/proof/blob/pinned/Theorem.lean#L37',
                        '<code>Exact.result</code>', '<script src="assets/films.js"></script>',
                        '<span class="dur">2:45</span>'):
            self.assertIn(literal, updated)
        for removed in ('INTERNAL', 'Canvas implementation', './tbook', 'Released yesterday', 'PIN', 'FILMS 1'):
            self.assertNotIn(removed, updated)
        self.assertIn('First &amp; Co · Second', updated)
        self.assertIn('<details class="lean"><summary>', updated)
        self.assertIn('English narration · Chinese and English subtitles', updated)
        self.assertIn('AI narration when relevant', updated)  # Story text is untouched.
        self.assertNotIn('<p class="meta"><span>English AI narration', updated)

    def test_repeated_site_hook_is_stable(self):
        updated = media.adapt_film_page(PAGE, WORK)
        self.assertEqual(media.adapt_film_page(updated, WORK), updated)

    def test_unrelated_page_is_untouched(self):
        self.assertEqual(media.adapt_film_page('<h1>Another page</h1>', WORK), '<h1>Another page</h1>')

    def test_malformed_duration_does_not_get_an_invented_length(self):
        with self.assertRaisesRegex(ValueError, 'unambiguous narrated duration'):
            media.adapt_film_page(PAGE.replace('<span class="dur">2:45</span>', ''), WORK)

    def test_proof_sources_are_never_silently_removed(self):
        with self.assertRaisesRegex(ValueError, 'proof sources'):
            media.adapt_film_page(PAGE.replace('<h4>Frozen sources</h4>', ''), WORK)


if __name__ == '__main__':
    unittest.main()
