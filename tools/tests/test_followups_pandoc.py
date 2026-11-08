"""Fenced code is seen the same way by every scanner: mdscan, the Pandoc stager, the math scanner.

A fence may sit in a block quote or a list item, and a ``> ```…`` line shown inside a
top-level code example is content, not a closing fence (:func:`tbook.mdscan.fence_end`).
:mod:`tbook.render` (via ``mdscan.parse_blocks``), :func:`tbook.pandoc._code_mask` and
:func:`tbook.mathrender.find_math` must agree on that, or a link or formula inside a code
example is rewritten by one target and shown as written by another.

Run: PYTHONPATH=tools .venv/bin/python -m unittest discover -s tools/tests -p 'test_followups_pandoc.py'
"""

from __future__ import annotations

import unittest

from tbook import mathrender, mdscan
from tbook import pandoc as tp

# A Markdown tutorial shows a quoted code block inside a top-level code example.
QUOTED_FENCE_IN_EXAMPLE = """\
Before $a$ here.

```markdown
> ```
> $x$ inside the example
> ```
$y$ still inside the example
```

After $b$ here.
"""

SAMPLES = {
    "quoted fence in an example": QUOTED_FENCE_IN_EXAMPLE,
    "fence in a block quote": "> ```\n> $x$\n> ```\n\n$b$\n",
    "fence in a nested list item": "- item\n\n  - nested\n\n    ```\n    $x$\n    ```\n\n$b$\n",
    "unclosed quoted fence ends with the quote": "> ```\n> $x$\n\n$b$\n",
    "longer closing fence": "````\n```\n$x$\n```\n`````\n$b$\n",
    "tilde fence with backticks inside": "~~~\n```\n$x$\n~~~\n$b$\n",
}


def math_hidden_lines(text: str) -> list[bool]:
    """Lines the math scanner masks completely (every character, or an empty line)."""
    mask, _ = mathrender._mask(text)
    out, offset = [], 0
    for line in text.split("\n"):
        out.append(all(mask[offset:offset + len(line)]))
        offset += len(line) + 1
    return out


class MathInCodeExampleTest(unittest.TestCase):
    def test_quoted_fence_line_does_not_close_the_example(self):
        spans, notes = mathrender.find_math(QUOTED_FENCE_IN_EXAMPLE)
        self.assertEqual([s.tex for s in spans], ["a", "b"])
        self.assertEqual(notes, [])

    def test_example_is_spliced_unchanged(self):
        spans, _ = mathrender.find_math(QUOTED_FENCE_IN_EXAMPLE)
        out = mathrender.splice(QUOTED_FENCE_IN_EXAMPLE, spans, ["<A>", "<B>"])
        self.assertIn("```markdown\n> ```\n> $x$ inside the example\n> ```\n$y$ still inside the example\n```", out)
        self.assertIn("Before <A> here.", out)
        self.assertIn("After <B> here.", out)

    def test_math_in_container_fences_is_not_math(self):
        for name, text in SAMPLES.items():
            with self.subTest(name):
                self.assertEqual([s.tex for s in mathrender.find_math(text)[0]],
                                 ["a", "b"] if "$a$" in text else ["b"])


class ScannersAgreeTest(unittest.TestCase):
    def test_same_fenced_lines(self):
        for name, text in SAMPLES.items():
            lines = text.split("\n")
            fenced = mdscan.fenced_code_lines(lines)
            with self.subTest(name):
                self.assertTrue(any(fenced))
                self.assertEqual(tp._code_mask(lines), fenced)
                hidden = math_hidden_lines(text)
                # Every fenced line is masked for math; blank lines outside code may be too.
                self.assertEqual([h for h, f, line in zip(hidden, fenced, lines) if line.strip()],
                                 [f for f, line in zip(fenced, lines) if line.strip()])

    def test_parse_blocks_sees_the_same_code(self):
        for name, text in SAMPLES.items():
            lines = text.split("\n")
            fenced = mdscan.fenced_code_lines(lines)
            code = [line for node in mdscan.parse_blocks(text) if isinstance(node, mdscan.Code) for line in node.lines]
            with self.subTest(name):
                self.assertEqual(code, [line for line, f in zip(lines, fenced) if f])


if __name__ == "__main__":
    unittest.main()
