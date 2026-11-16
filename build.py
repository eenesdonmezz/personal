"""Kişisel site üreticisi.

content/ içindeki Markdown dosyalarını templates/ içindeki Jinja2 şablonlarıyla
HTML'e çevirir ve sonucu docs/ klasörüne yazar (GitHub Pages bu klasörü yayınlar).

Kullanım:
    python build.py            # siteyi bir kez üretir
    python build.py --serve    # üretir, http://localhost:8000 adresinde açar,
                               # dosya değiştikçe otomatik yeniden üretir
"""

from __future__ import annotations

import argparse
import functools
import http.server
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from markupsafe import escape as escape_html

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "docs"

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
WORDS_PER_MINUTE = 200


@dataclass
class Page:
    slug: str
    meta: dict
    html: str
    words: int
    section: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.meta.get("title", self.slug)

    @property
    def date(self) -> date | None:
        return self.meta.get("date")

    @property
    def reading_time(self) -> int:
        return max(1, round(self.words / WORDS_PER_MINUTE))


def slugify(text: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    text = text.translate(table).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def tr_date(d: date | None) -> str:
    return f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}" if d else ""


def umlaut(text: str) -> Markup:
    """"ö"yü noktasız o + iki renkli nokta olarak çizer (ana sayfa başlığı)."""
    dotted = '<span class="umlaut">o<i class="dot b"></i><i class="dot y"></i></span>'
    return Markup(str(escape_html(text)).replace("ö", dotted))


def read_page(path: Path, section: str = "") -> Page:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(raw)
    meta, body = (yaml.safe_load(match[1]) or {}, match[2]) if match else ({}, raw)
    md = markdown.Markdown(extensions=["extra", "toc", "sane_lists", "smarty"])
    html = md.convert(body)
    words = len(re.findall(r"\w+", body))
    return Page(slug=path.stem, meta=meta, html=html, words=words,
                section=section, tags=meta.get("tags", []) or [])


def load_section(name: str) -> list[Page]:
    folder = CONTENT / name
    pages = [read_page(p, name) for p in sorted(folder.glob("*.md"))]
    pages = [p for p in pages if not p.meta.get("draft")]
    for p in pages:
        p.url = f"{name}/{p.slug}/"
    return sorted(pages, key=lambda p: p.date or date.min, reverse=True)


def write(rel: str, html: str) -> None:
    target = OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def build() -> None:
    config = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base_url = config.get("base_url", "").rstrip("/")

    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html"]))
    env.filters["tr_date"] = tr_date
    env.filters["slugify"] = slugify
    env.filters["umlaut"] = umlaut
    env.globals.update(site=config, year=date.today().year)

    # Klasörün kendisini değil içini temizle: Windows'ta açık bir sunucu
    # docs/ klasörünü kilitleyebiliyor.
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(STATIC, OUT / "static")
    (OUT / ".nojekyll").touch()

    # Profil fotoğrafı: proje klasöründeki profil.jpg/.jpeg/.png/.webp
    config["photo"] = ""
    for ext in ("jpg", "jpeg", "png", "webp", "JPG", "JPEG", "PNG"):
        photo = ROOT / f"profil.{ext}"
        if photo.exists():
            (OUT / "static" / "img").mkdir(parents=True, exist_ok=True)
            shutil.copy2(photo, OUT / "static" / "img" / photo.name)
            config["photo"] = f"static/img/{photo.name}"
            break

    def render(template: str, rel: str, **ctx) -> None:
        depth = rel.count("/")
        ctx["root"] = "../" * depth  # göreli linkler: site her alt klasörde çalışır
        write(rel, env.get_template(template).render(**ctx))

    posts = load_section("blog")
    # projeler frontmatter'daki "order" alanına göre sıralanır (küçük önce)
    projects = sorted(load_section("projeler"), key=lambda p: p.meta.get("order", 99))
    home = read_page(CONTENT / "index.md")
    about = read_page(CONTENT / "hakkimda.md")

    render("home.html", "index.html", page=home,
           posts=posts[:5], projects=projects[:4])
    render("page.html", "hakkimda/index.html", page=about)

    render("list.html", "blog/index.html", title="Yazılar", items=posts,
           tags=sorted({t for p in posts for t in p.tags}))
    for i, post in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        render("post.html", f"{post.url}index.html", page=post,
               newer=newer, older=older)

    for tag in {t for p in posts for t in p.tags}:
        tagged = [p for p in posts if tag in p.tags]
        render("list.html", f"etiket/{slugify(tag)}/index.html",
               title=f"Etiket: {tag}", items=tagged, tags=[])

    render("list.html", "projeler/index.html", title="Projeler", kind="projects",
           intro="Okulda ve En2Studios'ta üzerinde çalıştığım işler.",
           items=projects, tags=[])
    for proj in projects:
        render("post.html", f"{proj.url}index.html", page=proj,
               newer=None, older=None)

    render("404.html", "404.html")

    # RSS ve sitemap: base_url verilmişse mutlak linklerle üretilir
    if base_url:
        items = "".join(
            f"<item><title>{escape(p.title)}</title>"
            f"<link>{base_url}/{p.url}</link><guid>{base_url}/{p.url}</guid>"
            f"<description>{escape(p.meta.get('description', ''))}</description></item>"
            for p in posts)
        write("feed.xml",
              f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
              f"<title>{escape(config['name'])}</title><link>{base_url}/</link>"
              f"<description>{escape(config.get('description', ''))}</description>"
              f"{items}</channel></rss>")
        urls = ["", "hakkimda/", "blog/", "projeler/"] + [p.url for p in posts + projects]
        write("sitemap.xml",
              '<?xml version="1.0" encoding="UTF-8"?>'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              + "".join(f"<url><loc>{base_url}/{u}</loc></url>" for u in urls)
              + "</urlset>")

    print(f"✓ Site üretildi: {len(posts)} yazı, {len(projects)} proje → docs/")


def snapshot() -> dict[Path, float]:
    files = [ROOT / "site.yml"] + list(ROOT.glob("profil.*"))
    for folder in (CONTENT, TEMPLATES, STATIC):
        files += [p for p in folder.rglob("*") if p.is_file()]
    return {p: p.stat().st_mtime for p in files}


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(OUT))
    server = http.server.ThreadingHTTPServer(("localhost", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"→ http://localhost:{port}  (durdurmak için Ctrl+C)")
    last = snapshot()
    try:
        while True:
            time.sleep(1)
            now = snapshot()
            if now != last:
                last = now
                try:
                    build()
                except Exception as exc:  # yazım hatası sunucuyu düşürmesin
                    print(f"✗ Hata: {exc}")
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kişisel site üreticisi")
    parser.add_argument("--serve", action="store_true", help="yerelde önizle")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda Türkçe karakterler
    build()
    if args.serve:
        serve(args.port)
