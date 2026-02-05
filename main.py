import json
import time
import html
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://dizipal.uk/filmler"
OUT_JSON = "films.json"
OUT_HTML = "index.html"

scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "mobile": False,
    }
)


def get_soup(url: str) -> BeautifulSoup | None:
    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("HATA:", url, e)
        return None


def get_video_link(detail_url: str) -> str:
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


def get_film_info(item, base_domain: str) -> dict | None:
    a = item.find("a")
    img = item.find("img")
    if not a or not img:
        return None

    title = html.unescape(a.get("title", "").strip())
    if not title:
        return None

    href = a.get("href", "")
    url = urljoin(base_domain, href)

    image = img.get("data-src") or img.get("src") or ""
    if image.startswith("//"):
        image = "https:" + image

    return {
        "id": None,
        "title": title,
        "image": image,
        "url": url,
        "videoUrl": "",
        "year": "",
        "duration": "",
        "imdb": "",
        "genres": [],
        "summary": "",
    }


def get_films(limit: int = 60) -> list[dict]:
    films: list[dict] = []
    seen: set[str] = set()
    page = 1

    while True:
        page_url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}/"
        print("Sayfa:", page_url)

        soup = get_soup(page_url)
        if not soup:
            break

        items = soup.select("div.post-item")
        if not items:
            break

        added = 0
        for item in items:
            film = get_film_info(item, BASE_URL)
            if not film:
                continue
            if film["title"] in seen:
                continue

            print("Film:", film["title"])
            film["videoUrl"] = get_video_link(film["url"])

            films.append(film)
            seen.add(film["title"])
            added += 1

            time.sleep(0.2)

            if len(films) >= limit:
                return films

        if added == 0:
            break

        page += 1

    return films


def generate_html(films: list[dict]) -> str:
    cards = ""
    for f in films:
        cards += f"""
        <div class="card">
            <img src="{f['image']}" alt="{f['title']}">
            <h3>{f['title']}</h3>
            <a href="{f['videoUrl']}" target="_blank">▶ İzle</a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Film Arşivi</title>
<style>
body {{ background:#0f0f0f; color:#fff; font-family:Arial; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:15px; }}
.card {{ background:#1a1a1a; padding:10px; border-radius:8px; text-align:center; }}
.card img {{ width:100%; border-radius:6px; }}
.card a {{ display:block; margin-top:8px; color:#0f0; text-decoration:none; }}
</style>
</head>
<body>
<h1>🎥 Film Listesi ({len(films)})</h1>
<div class="grid">{cards}</div>
</body>
</html>"""


if __name__ == "__main__":
    films = get_films()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(films, f, ensure_ascii=False, indent=2)

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(generate_html(films))

    print(f"OK: {len(films)} film")
