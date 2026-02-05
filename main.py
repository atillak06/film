import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import html
from urllib.parse import urljoin

BASE_URL = "https://dizipal.uk/filmler"
OUT_JSON = "films.json"
OUT_HTML = "index.html"

# Cloudflare uyumlu scraper
scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "desktop": True
    }
)

# ------------------------------------------------
def get_soup(url):
    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("HATA:", url, e)
        return None

# ------------------------------------------------
# Film detay sayfasından iframe linki
def get_video_link(detail_url):
    soup = get_soup(detail_url)
    if not soup:
        return ""

    iframe = soup.find("iframe")
    if not iframe:
        return ""

    src = iframe.get("src", "")
    if src.startswith("//"):
        src = "https:" + src

    return src

# ------------------------------------------------
# Liste sayfasındaki film kartı
def get_film_info(item, base_domain):
    try:
        a = item.find("a")
        img = item.find("img")
        if not a or not img:
            return None

        title = html.unescape(a.get("title", "").strip())
        if not title:
            return None

        url = urljoin(base_domain, a.get("href"))
        image = img.get("data-src") or img.get("src") or ""
        if image.startswith("//"):
            image = "https:" + image

        return {
            "title": title,
            "image": image,
            "url": url,
            "videoUrl": ""
        }
    except:
        return None

# ------------------------------------------------
def get_films():
    films = []
    seen = set()
    page = 1

    while True:
        page_url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}/"
        print(f"📄 Sayfa: {page_url}")

        soup = get_soup(page_url)
        if not soup:
            break

        items = soup.select("div.post-item")
        if not items:
            break

        new_count = 0

        for item in items:
            film = get_film_info(item, BASE_URL)
            if not film or film["title"] in seen:
                continue

            print("🎬 Film:", film["title"])

            # iframe isteği pahalı → yavaşlat
            film["videoUrl"] = get_video_link(film["url"])

            films.append(film)
            seen.add(film["title"])
            new_count += 1

            time.sleep(1.2)  # 🔴 Actions için şart

        if new_count == 0:
            break

        if len(films) >= 60:  # güvenlik limiti
            print("Güvenlik limiti.")
            break

        page += 1

    return films

# ------------------------------------------------
def generate_html(films):
    cards = ""
    for f in films:
        cards += f"""
        <div class="card">
            <img src="{f['image']}" alt="{f['title']}">
            <h3>{f['title']}</h3>
            <a href="{f['videoUrl']}" target="_blank">▶ İzle</a>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Film Arşivi</title>
<style>
body {{
    background:#0f0f0f;
    color:#fff;
    font-family:Arial;
}}
.grid {{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
    gap:15px;
}}
.card {{
    background:#1a1a1a;
    padding:10px;
    border-radius:8px;
    text-align:center;
}}
.card img {{
    width:100%;
    border-radius:6px;
}}
.card a {{
    display:block;
    margin-top:8px;
    color:#0f0;
    text-decoration:none;
}}
</style>
</head>
<body>

<h1>🎥 Film Listesi ({len(films)})</h1>
<div class="grid">
{cards}
</div>

</body>
</html>
"""

# ------------------------------------------------
films = get_films()

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(films, f, ensure_ascii=False, indent=2)

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(generate_html(films))

print(f"✅ {len(films)} film kaydedildi")
print("📄 films.json + index.html oluşturuldu")
