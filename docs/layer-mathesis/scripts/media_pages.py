"""Adapt the upstream film page's reader copy without replacing its player or theme."""
import html
from html.parser import HTMLParser
import re


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text, self.nodes, self.stack = text, [], []
        self.lines = [0]
        for match in re.finditer("\n", text):
            self.lines.append(match.end())
        self.feed(text)

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            return
        start = self.position()
        node = {"tag": tag, "attrs": dict(attrs), "start": start,
                "content": start + len(self.get_starttag_text())}
        self.stack.append(node)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]["tag"] != tag:
            return
        node = self.stack.pop()
        node.update(stop=self.position(), end=self.text.index(">", self.position()) + 1)
        self.nodes.append(node)


def bilingual(zh, en):
    return f'<span class="zh">{zh}</span><span class="en">{en}</span>'


def adapt_film_page(text, work):
    """Keep original media/evidence URLs and language controls; change presentation only."""
    if 'content="tbook film"' not in text or 'data-mathesis-media="1"' in text:
        return text
    nodes = Elements(text).nodes
    edits = []
    title = bilingual("视频讲解", "Video explanation")
    for node in nodes:
        tag, attrs = node["tag"], node["attrs"]
        classes = set(attrs.get("class", "").split())
        replacement = None
        if tag == "section" and "hero" in classes:
            replacement = ""
        elif "pill" in classes:
            replacement = ""
        elif tag == "h1" and "logo" in classes:
            replacement = f'<h1 class="logo">{title}</h1>'
        elif "tagline" in classes:
            replacement = '<div class="tagline">' + bilingual("从问题到关键思路", "From the question to the key idea") + '</div>'
        elif tag == "p" and "meta" in classes:
            replacement = '<p class="meta">' + bilingual("英文旁白 · 中英双语字幕", "English narration · Chinese and English subtitles") + '</p>'
        elif tag == "p" and "kicker" in classes:
            durations = [n for n in nodes if n["tag"] == "span" and "dur" in n["attrs"].get("class", "").split()
                         and node["content"] <= n["start"] < n["end"] <= node["stop"]]
            if len(durations) != 1:
                raise ValueError("film page has no unambiguous narrated duration")
            duration = durations[0]
            replacement = '<p class="kicker">' + title + ' · ' + text[duration["start"]:duration["end"]] + '</p>'
        elif tag == "div" and "lean" in classes:
            headings = [n for n in nodes if n["tag"] == "h4" and node["content"] <= n["start"] < n["end"] <= node["stop"]]
            if len(headings) != 1:
                raise ValueError("film page proof sources have no unambiguous heading")
            heading = headings[0]
            content = (text[node["content"]:heading["start"]] + '<summary>' +
                       bilingual("查看形式化依据", "Formal proof sources") + '</summary>' +
                       text[heading["end"]:node["stop"]])
            replacement = '<details class="lean">' + content + '</details>'
        elif tag == "footer" and "foot" in classes:
            authors = " · ".join(html.escape(author["name"]) for author in work["authors"])
            replacement = '<footer class="foot"><span>' + authors + '</span><span>Mathesis · ' + html.escape(work["license"]) + '</span></footer>'
        elif tag == "title":
            replacement = '<title>视频讲解 · Mathesis</title>'
        if replacement is not None:
            edits.append((node["start"], node["end"], replacement))
    # Removing an outer explanatory block also removes its children.
    accepted = []
    for start, end, replacement in sorted(edits):
        if not accepted or start >= accepted[-1][1]:
            accepted.append((start, end, replacement))
    for start, end, replacement in reversed(accepted):
        text = text[:start] + replacement + text[end:]
    text = re.sub(r'data-title-zh="[^"]*"', 'data-title-zh="视频讲解 · Mathesis"', text, count=1)
    text = re.sub(r'data-title-en="[^"]*"', 'data-title-en="Video explanation · Mathesis"', text, count=1)
    return text.replace("<html ", '<html data-mathesis-media="1" ', 1)


def adapt_media_pages(out, slug, work):
    page = out / slug / "films/index.html"
    if page.is_file():
        if page.is_symlink() or not page.resolve().is_relative_to(out.resolve()):
            raise ValueError("unsafe film page")
        original = page.read_text(encoding="utf-8")
        updated = adapt_film_page(original, work)
        if updated != original:
            page.write_text(updated, encoding="utf-8")
