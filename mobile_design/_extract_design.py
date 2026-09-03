#!/usr/bin/env python3
"""Extract the design document from a Claude bundled-artifact HTML export.

Reads `NREGA Companion App Design.html` (or the first *.html arg), unescapes the
embedded template JSON, and writes two files next to it:
  - design_doc.html  : the raw design document (open in a browser to see visuals)
  - design_spec.md   : readable text (screens/spec/A–H), SVG visuals stripped

Usage: python3 mobile_design/_extract_design.py [export.html]
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
bundle_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "NREGA Companion App Design.html"
out_html = HERE / "design_doc.html"
out_md = HERE / "design_spec.md"

raw = bundle_path.read_text(encoding="utf-8")
m = re.search(r'<script type="__bundler/template">\s*(.*?)\s*</script>', raw, re.S)
if not m:
    sys.exit("template script not found in bundle")
doc = json.loads(m.group(1))
out_html.write_text(doc, encoding="utf-8")
print(f"wrote {out_html} ({len(doc):,} chars)")


class Md(HTMLParser):
    """HTML -> markdown-ish text. Drops <svg> visuals and <style>/<script>."""

    BLOCK = {
        "p", "div", "section", "li", "tr", "pre", "blockquote", "ul", "ol",
        "table", "tbody", "thead", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
        "br", "x-dc", "helmet", "body", "html",
    }
    H = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}
    HEADING_CLASS = {"k": "#### ", "h2": "## ", "h3": "### ", "h4": "#### "}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0
        self.in_pre = 0
        self.in_cell = False
        self.cell_open = False
        self.pending_space = False
        self.pending_newlines = 0

    def _newlines(self, n):
        if self.skip_depth or self.in_pre:
            return
        if self.out and self.out[-1] != "\n":
            self.out.append("\n")
        if n > 1 and not (self.out and self.out[-1] == "\n"):
            self.out.append("\n")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag in ("style", "script", "svg"):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "svg":
            self.skip_depth += 1
            return
        if tag == "pre":
            self.in_pre += 1
            self._newlines(2)
            self.out.append("```\n")
            return
        if tag in self.BLOCK or tag == "br":
            if tag == "li":
                self._newlines(1)
                self.out.append("- ")
            elif tag == "tr":
                self._newlines(1)
            elif tag == "td" or tag == "th":
                self.in_cell = True
                self.cell_open = False
                return
            elif tag in ("tbody", "thead", "table"):
                self._newlines(1)
            else:
                self._newlines(1)
        if tag in self.H:
            self.out.append("\n" + self.H[tag])
        elif tag in ("h1", "h2", "h3", "h4"):
            pass
        # class-based headings inside <p class="h2|h3|h4|k">
        if cls in self.HEADING_CLASS and not self.in_cell:
            self.out.append("\n" + self.HEADING_CLASS[cls])
        if tag in ("td", "th"):
            if not self.cell_open:
                self.out.append(" | ")
                self.cell_open = True
        if tag == "b" or tag == "strong":
            self.out.append("**")
        if tag == "i" or tag == "em":
            self.out.append("*")
        if tag == "code" or (tag == "span" and "mono" in cls):
            self.out.append("`")
        if tag in ("ul", "ol"):
            self._newlines(1)

    def handle_endtag(self, tag):
        if tag in ("style", "script", "svg"):
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "pre":
            self.out.append("\n```\n")
            self.in_pre = max(0, self.in_pre - 1)
            return
        if tag in ("b", "strong"):
            self.out.append("**")
        if tag in ("i", "em"):
            self.out.append("*")
        if tag == "code":
            self.out.append("`")
        if tag in ("td", "th"):
            self.in_cell = False
            self.cell_open = False
        if tag == "li":
            self._newlines(1)
        if tag == "p":
            self._newlines(2)

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_pre:
            self.out.append(data)
            return
        if not data.strip():
            return
        if self.in_cell:
            text = data.strip()
            if text:
                self.out.append(text)
            return
        # collapse inline whitespace, then squeeze
        self.out.append(data)

    def finish(self):
        text = "".join(self.out)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"\n *\n(\*|#)", r"\n\n\1", text)
        return text.strip()


p = Md()
p.feed(doc)
text = p.finish()
# heading lines should stand alone
text = re.sub(r"(?m)^(#{1,6} )", r"\n\1", text)
text = re.sub(r"\n{3,}", "\n\n", text)
out_md.write_text(text, encoding="utf-8")
print(f"wrote {out_md} ({len(text):,} chars)")
