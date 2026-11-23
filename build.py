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
import hashlib
import functools
import http.server
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timezone, timedelta
from email.utils import format_datetime
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
TR_TZ = timezone(timedelta(hours=3))


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

    @property
    def sample(self) -> bool:
        """Örnek içerik: sayfada "örnek" rozetiyle gösterilir."""
        return bool(self.meta.get("sample"))


def slugify(text: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    text = text.translate(table).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def tr_date(d: date | None) -> str:
    return f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}" if d else ""


def rfc822(d: date) -> str:
    return format_datetime(datetime.combine(d, dtime(9, 0), TR_TZ))


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


def load_section_in(folder: Path, url_prefix: str) -> list[Page]:
    """folder içindeki .md dosyaları; adresleri url_prefix + slug/ olur."""
    pages = [read_page(p, folder.name) for p in sorted(folder.glob("*.md"))]
    pages = [p for p in pages if not p.meta.get("draft")]
    for p in pages:
        p.url = f"{url_prefix}{p.slug}/"
    return sorted(pages, key=lambda p: p.date or date.min, reverse=True)


def write(rel: str, html: str) -> None:
    target = OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


# Arayüz yazıları. Türkçe kökte, İngilizce /en/ altında üretilir.
LANGS = {
    "tr": {
        "prefix": "", "content": CONTENT, "locale": "tr_TR",
        "about": "hakkimda", "contact": "iletisim", "blog": "blog", "tag": "etiket",
        "months": TR_MONTHS,
        "t": {
            "skip": "İçeriğe geç", "menu": "Ana menü",
            "switch_label": "EN", "switch_title": "English",
            "footer_cta": "Bir fikrin ya da sorun varsa yaz:",
            "posts": "Yazılar", "see_all": "Hepsini gör", "projects": "Projeler",
            "all": "Hepsi", "tags": "Etiketler", "empty": "Burada henüz bir şey yok.",
            "min_short": "dk okuma", "min_long": "dakikalık okuma",
            "all_posts": "Bütün yazılar", "all_projects": "Bütün projeler",
            "older": "Önceki yazı", "newer": "Sonraki yazı", "more_posts": "Diğer yazılar",
            "cv_title": "Özgeçmiş (CV)", "cv_sub": "PDF olarak indir",
            "cv_updated": "son güncelleme", "cv_btn": "CV'yi indir",
            "coming": "Eklenecek", "tag_title": "Etiket",
            "blog_intro": "Üniversite, teknoloji, hobiler ve seyahat üzerine yazılar.",
            "projects_intro": "Üzerinde çalıştığım işler.",
        },
    },
    "en": {
        "prefix": "en/", "content": CONTENT / "en", "locale": "en_US",
        "about": "about", "contact": "contact", "blog": "blog", "tag": "tag",
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
        "t": {
            "skip": "Skip to content", "menu": "Main menu",
            "switch_label": "TR", "switch_title": "Türkçe",
            "footer_cta": "Have an idea or a question? Write to me:",
            "posts": "Posts", "see_all": "See all", "projects": "Projects",
            "all": "All", "tags": "Tags", "empty": "Nothing here yet.",
            "min_short": "min read", "min_long": "min read",
            "all_posts": "All posts", "all_projects": "All projects",
            "older": "Previous post", "newer": "Next post", "more_posts": "More posts",
            "cv_title": "Résumé (CV)", "cv_sub": "Download as PDF",
            "cv_updated": "last updated", "cv_btn": "Download CV",
            "coming": "Coming soon", "tag_title": "Tag",
            "blog_intro": "Posts about university, technology, hobbies and travel.",
            "projects_intro": "Things I have worked on.",
        },
    },
}


def build() -> None:
    raw_config = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base_url = raw_config.get("base_url", "").rstrip("/")
    raw_config["base_url"] = base_url

    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html"]))
    env.filters["slugify"] = slugify
    env.filters["umlaut"] = umlaut
    # Stil ve betik değişince adres de değişsin: tarayıcılar eski dosyayı kullanmasın
    asset_v = hashlib.md5(b"".join((STATIC / f).read_bytes() for f in ("style.css", "bg.js"))).hexdigest()[:8]
    env.globals.update(year=date.today().year, asset_v=asset_v)

    # Klasörün kendisini değil içini temizle: Windows'ta açık bir sunucu
    # docs/ klasörünü kilitleyebiliyor.
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(STATIC, OUT / "static")
    (OUT / ".nojekyll").touch()

    # Profil fotoğrafı: gorsel/ (ya da proje kökündeki) profil.jpg/.jpeg/.png/.webp
    raw_config["photo"] = ""
    candidates = [folder / f"profil.{ext}" for folder in (ROOT / "gorsel", ROOT)
                  for ext in ("jpg", "jpeg", "png", "webp", "JPG", "JPEG", "PNG")]
    for photo in candidates:
        if photo.exists():
            (OUT / "static" / "img").mkdir(parents=True, exist_ok=True)
            shutil.copy2(photo, OUT / "static" / "img" / photo.name)
            raw_config["photo"] = f"static/img/{photo.name}"
            break

    # CV: site.yml'deki dosya static/ altında varsa Hakkımda'da indirme düğmesi çıkar
    cv_file = (raw_config.get("cv") or {}).get("file", "")
    raw_config["cv_file"] = cv_file if cv_file and (ROOT / cv_file).exists() else ""

    sitemap: list[tuple[str, date | None]] = []
    summary = []

    # Önce her dilin içeriğini yükle: dil düğmesi karşı dildeki sayfayı bilmeli
    loaded = {}
    for lang, L in LANGS.items():
        if lang != "tr" and not (L["content"] / "index.md").exists():
            continue
        posts = load_section_in(L["content"] / "blog", f"{L['prefix']}{L['blog']}/")
        projects = sorted(load_section_in(L["content"] / "projeler",
                                          f"{L['prefix']}projeler/"),
                          key=lambda p: p.meta.get("order", 99))
        loaded[lang] = (posts, projects)

    def counterpart(lang: str, kind: str, slug: str = "") -> str | None:
        """Diğer dildeki karşılık gelen sayfanın yolu (yoksa o dilin ana sayfası)."""
        other = "en" if lang == "tr" else "tr"
        if other not in loaded:
            return None
        O = LANGS[other]
        if kind in ("about", "contact"):
            return f"{O['prefix']}{O[kind]}/"
        if kind == "blog":
            return f"{O['prefix']}{O['blog']}/"
        if kind == "post":
            match = [p for p in loaded[other][0] if p.slug == slug]
            return match[0].url if match else f"{O['prefix']}{O['blog']}/"
        return O["prefix"]

    for lang, (posts, projects) in loaded.items():
        L = LANGS[lang]
        t = L["t"]
        prefix = L["prefix"]
        config = {**raw_config, **(raw_config.get(lang) or {})} if lang != "tr" else dict(raw_config)
        # Arama motorları için "bu profiller de benim" listesi (e-posta hariç)
        config["same_as"] = [c["href"] for c in config.get("contact", [])
                             if c.get("href", "").startswith("http")]
        months = L["months"]
        env.filters["tr_date"] = (lambda d, m=months:
                                  (f"{d.day} {m[d.month - 1]} {d.year}" if lang == "tr"
                                   else f"{m[d.month - 1]} {d.day}, {d.year}") if d else "")

        def render(template: str, rel: str, alt: str | None = None, **ctx) -> None:
            depth = rel.count("/")
            ctx["root"] = "../" * depth  # göreli linkler: site her alt klasörde çalışır
            path = rel.removesuffix("index.html")
            ctx.update(path=path, site=config, tx=t, lang=lang, prefix=prefix,
                       locale=L["locale"], blog_dir=f"{prefix}{L['blog']}/",
                       tag_dir=f"{prefix}{L['tag']}/", alt=alt,
                       alt_lang="en" if lang == "tr" else "tr")
            ctx["canonical"] = f"{base_url}/{path}" if base_url else ""
            ctx["alt_url"] = f"{base_url}/{alt}" if base_url and alt is not None else ""
            write(rel, env.get_template(template).render(**ctx))
            sitemap.append((path, ctx.get("page").date if isinstance(ctx.get("page"), Page) else None))

        content = L["content"]
        home = read_page(content / "index.md")
        about = read_page(content / ("hakkimda.md" if lang == "tr" else "about.md"))
        contact = read_page(content / ("iletisim.md" if lang == "tr" else "contact.md"))
        all_tags = sorted({tg for p in posts for tg in p.tags})
        tag_counts = {tg: sum(tg in p.tags for p in posts) for tg in all_tags}

        render("home.html", f"{prefix}index.html", alt=counterpart(lang, "home"),
               page=home, posts=posts[:3], projects=projects[:4])
        render("about.html", f"{prefix}{L['about']}/index.html",
               alt=counterpart(lang, "about"), page=about)
        render("contact.html", f"{prefix}{L['contact']}/index.html",
               alt=counterpart(lang, "contact"), page=contact)

        render("list.html", f"{prefix}{L['blog']}/index.html", alt=counterpart(lang, "blog"),
               title=t["posts"], intro=t["blog_intro"],
               items=posts, tags=all_tags, tag_counts=tag_counts)
        for i, post in enumerate(posts):
            newer = posts[i - 1] if i > 0 else None
            older = posts[i + 1] if i + 1 < len(posts) else None
            render("post.html", f"{post.url}index.html",
                   alt=counterpart(lang, "post", post.slug), page=post,
                   newer=newer, older=older, og_type="article")

        for tag in all_tags:
            tagged = [p for p in posts if tag in p.tags]
            render("list.html", f"{prefix}{L['tag']}/{slugify(tag)}/index.html",
                   alt=counterpart(lang, "blog"),
                   title=f"{t['tag_title']}: {tag}", items=tagged, tags=all_tags,
                   tag_counts=tag_counts, current_tag=tag)

        # Projeler sayfası sadece projeler/ içinde dosya varsa üretilir
        if projects:
            render("list.html", f"{prefix}projeler/index.html", title=t["projects"],
                   kind="projects", intro=t["projects_intro"], items=projects, tags=[])
        for proj in projects:
            render("post.html", f"{proj.url}index.html", page=proj, newer=None, older=None)

        if lang == "tr":
            render("404.html", "404.html")
            sitemap.pop()  # 404 sayfası sitemap'e girmez

        summary.append(f"{lang}: {len(posts)} yazı")

    if base_url:
        write("sitemap.xml",
              '<?xml version="1.0" encoding="UTF-8"?>'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              + "".join(f"<url><loc>{base_url}/{u}</loc>"
                        + (f"<lastmod>{d.isoformat()}</lastmod>" if d else "")
                        + "</url>" for u, d in sitemap)
              + "</urlset>")

    print(f"✓ Site üretildi ({', '.join(summary)}) → docs/")


def snapshot() -> dict[Path, float]:
    files = [ROOT / "site.yml"] + list(ROOT.glob("profil.*")) + list(ROOT.glob("gorsel/profil.*"))
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
