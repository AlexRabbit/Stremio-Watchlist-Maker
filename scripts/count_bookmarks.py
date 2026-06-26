"""Count links in Entretenimiento > Peliculas bookmarks folder."""
from __future__ import annotations

import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.in_target = False
        self.depth = 0
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if tag == "h3":
            title = (attrs_d.get("add_date") and "") or ""
            self._pending_h3 = True
        elif tag == "h3":
            pass
        if tag == "dl":
            self.depth += 1
        if tag == "h3":
            self.stack.append("")
            self._capture_h3 = True
        elif tag == "a" and "href" in attrs_d:
            self._pending_link = attrs_d["href"] or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "dl":
            self.depth -= 1
            if self.in_target and self.depth == 0:
                self.in_target = False
        if tag == "h3" and self.stack:
            name = self.stack[-1].strip()
            if name.lower() == "peliculas" and "entretenimiento" in [s.lower() for s in self.stack[:-1]]:
                self.in_target = True
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if getattr(self, "_capture_h3", False):
            if self.stack:
                self.stack[-1] += data
            self._capture_h3 = False
        if getattr(self, "_pending_link", None) is not None and self.in_target:
            href = self._pending_link
            title = data.strip()
            if href and title:
                self.links.append((href, title))
            self._pending_link = None


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "bookmarks.html")
    html = path.read_text(encoding="utf-8", errors="replace")
    # Simpler regex approach for Peliculas block
    m = re.search(
        r"<DT><H3[^>]*>Peliculas</H3>\s*<DL><p>(.*?)(?=<DT><H3|<DT><A HREF=\"https://www\.youtube\.com/@)",
        html,
        re.I | re.S,
    )
    if not m:
        # fallback: from Peliculas to end of parent DL
        start = html.lower().find(">peliculas</h3>")
        if start < 0:
            print("Peliculas folder not found")
            return
        chunk = html[start:]
        end = chunk.find("</DL><p>", 20)
        section = chunk[:end] if end > 0 else chunk
    else:
        section = m.group(1)
    links = re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', section, re.I)
    print("Total links:", len(links))
    domains: Counter[str] = Counter()
    for url, _ in links:
        d = re.sub(r"^https?://(www\.)?", "", url.lower()).split("/")[0]
        domains[d] += 1
    for d, c in domains.most_common(20):
        print(f"  {c:4d}  {d}")


if __name__ == "__main__":
    main()
