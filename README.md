# Kişisel Web Sitesi

Python ile yazılmış küçük bir statik site üreticisiyle yapılan kişisel web sitem.
İçerik Markdown ile yazılır, `build.py` bunu Jinja2 şablonlarıyla HTML'e çevirip
`docs/` klasörüne koyar, GitHub Pages da bu klasörü yayınlar.

## Özellikler

- Markdown + YAML frontmatter ile yazı ve proje sayfaları
- Otomatik blog listesi, tarih sıralama, okuma süresi, etiket sayfaları
- Önceki / sonraki yazı gezinmesi
- Proje galerisi (kart görseli isteğe bağlı), Hakkımda + indirilebilir CV, İletişim sayfası
- RSS beslemesi ve sitemap (`site.yml` içinde `base_url` verilince)
- SEO: canonical link, Open Graph / X paylaşım önizlemeleri, schema.org verisi
- Açık / koyu tema: sistem ayarına uyar, menüdeki düğmeyle değiştirilir ve hatırlanır
- Mobil uyumlu tasarım
- `sample: true` olan yazı ve projeler "Örnek" rozetiyle gösterilir
- Yerel önizleme sunucusu: dosya kaydedince site kendini yeniden üretir

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Kullanım

```bash
python build.py            # siteyi docs/ klasörüne üretir
python build.py --serve    # http://localhost:8000 adresinde canlı önizleme
```

## Klasör yapısı

| Yol | Ne işe yarar |
| --- | --- |
| `site.yml` | Ad, menü, site adresi, CV dosyası, iletişim kartları |
| `content/index.md` | Ana sayfadaki tanıtım yazısı |
| `content/hakkimda.md` | Hakkımda sayfası |
| `content/iletisim.md` | İletişim sayfasının giriş yazısı |
| `static/cv/enes-donmez-cv.pdf` | İndirilebilir CV (dosya konunca Hakkımda'da düğme çıkar) |
| `content/blog/*.md` | Blog yazıları |
| `content/projeler/*.md` | Projeler |
| `templates/` | Jinja2 HTML şablonları |
| `static/` | CSS ve görseller |
| `docs/` | Üretilen site (elle düzenlenmez) |

## Yeni yazı eklemek

`content/blog/yazi-adi.md` dosyası oluştur:

```markdown
---
title: "Yazının başlığı"
date: 2026-11-20
description: "Kısa açıklama"
tags: [etiket1, etiket2]
---

Yazının metni...
```

Sonra `python build.py` çalıştırıp değişiklikleri commit'le ve pushla.
`draft: true` eklersen yazı yayınlanmaz.
