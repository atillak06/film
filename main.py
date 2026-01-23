import requests
from bs4 import BeautifulSoup
import json
import os
import time
import html
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_soup(url, method='GET', data=None):
    """Standart Requests ile siteye baglanir."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': BASE_URL,
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=data, timeout=15)
        else:
            response = requests.get(url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        if method == 'POST':
            try:
                return response.json()
            except:
                return None
                
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Baglanti Hatasi ({url}): {e}")
        return None

def get_movie_details(movie_url):
    """Filmin detaylarina girer."""
    info = {
        'videoUrl': movie_url,
        'summary': 'Özet bulunamadı.',
        'genres': ['Genel'],
        'duration': 'Belirtilmemiş'
    }
    
    soup = get_soup(movie_url)
    if not soup:
        return info

    try:
        # 1. Video Linki
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            info['videoUrl'] = iframe['src']
            
        # 2. Ozet
        summary_el = soup.select_one('.ozet-text') or soup.select_one('.summary') or soup.find('article')
        if summary_el:
            info['summary'] = html.unescape(summary_el.text.strip())
            
        # 3. Turler
        genre_links = soup.select('.tur a') or soup.select('.genres a')
        if genre_links:
            info['genres'] = [html.unescape(g.text.strip()) for g in genre_links]
            
        # 4. Sure
        duration_el = soup.select_one('.sure') or soup.select_one('.duration')
        if duration_el:
            info['duration'] = html.unescape(duration_el.text.strip())
            
    except Exception as e:
        print(f"Detay hatasi: {e}")
        
    return info

def parse_films_from_list(soup, base_domain):
    """Listeden temel bilgileri alir."""
    films = []
    elements = soup.select('li.movie-item') or soup.select('li.item') or soup.find_all('li')

    for el in elements:
        try:
            link_el = el.find('a')
            if not link_el: continue
            
            movie_id = link_el.get('data-id')
            href = link_el.get('href', '')
            
            if href and not href.startswith('http'):
                full_url = base_domain + href
            else:
                full_url = href

            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "Isimsiz"

            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            if title != "Isimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": html.unescape(title),
                    "image": image,
                    "url": full_url,
                    "imdb": imdb,
                    "year": year
                })
        except:
            continue
    return films

def get_all_films():
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tarama Baslatiliyor: {BASE_URL}")
    
    # --- 1. SAYFA ---
    soup = get_soup(BASE_URL)
    if not soup:
        print("Siteye erisilemedi.")
        return []

    new_films = parse_films_from_list(soup, base_domain)
    
    for f in new_films:
        if f['title'] not in processed_titles:
            print(f">> Detaylar: {f['title']}")
            details = get_movie_details(f['url'])
            f.update(details)
            all_films.append(f)
            processed_titles.add(f['title'])
            time.sleep(0.2)
            
    print(f"Sayfa 1 Bitti. ({len(all_films)} Film)")

    # --- 2. DONGU ---
    page = 1
    MAX_PAGES = 30 
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id: break
            
        print(f"Siradaki sayfa (Ref: {last_id})...")
        
        payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
        data = get_soup(api_url, method='POST', data=payload)
        
        if not data or not data.get('html'):
            break
            
        html_part = BeautifulSoup(data['html'], 'html.parser')
        more_films = parse_films_from_list(html_part, base_domain)
        
        added_count = 0
        for f in more_films:
            if f['title'] not in processed_titles:
                details = get_movie_details(f['url'])
                f.update(details)
                all_films.append(f)
                processed_titles.add(f['title'])
                added_count += 1
                time.sleep(0.2)
        
        if added_count == 0:
            break
            
        page += 1
        print(f"Sayfa {page} Tamam. Toplam: {len(all_films)}")

    return all_films

def get_all_genres(films):
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
    films_json = json.dumps(films, ensure_ascii=False)
    all_genres = get_all_genres(films)
    genres_json = json.dumps(all_genres, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Film Arsivi</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 0; background-color: #344966; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #2c3e50; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; }}
        h1 {{ margin: 0; font-size: 1.2em; }}
        .controls {{ display: flex; gap: 10px; }}
        #genreSelect, #searchInput {{ padding: 8px; border-radius: 5px; border: none; background: #496785; color: white; }}
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; margin-top: 70px; padding: 20px; }}
        .film-card {{ border-radius: 8px; background: #496785; overflow: hidden; cursor: pointer; transition: transform 0.2s; }}
        .film-card:hover {{ transform: translateY(-5px); }}
        .film-card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        .film-title {{ padding: 10px; text-align: center; font-size: 0.9em; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); }}
        .modal-content {{ background: #2c3e50; margin: 10% auto; padding: 25px; width: 90%; max-width: 500px; border-radius: 8px; position: relative; }}
        .close {{ position: absolute; top: 10px; right: 20px; font-size: 30px; cursor: pointer; }}
        .btn-watch {{ display: block; background: #e74c3c; color: white; text-align: center; padding: 10px; border-radius: 5px; text-decoration: none; margin-top: 20px; font-weight: bold; }}
        .meta-tag {{ display: inline-block; background: #344966; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; margin: 5px 5px 5px 0; }}
        #loadMore {{ display: block; margin: 20px auto; padding: 10px 30px; background: #f39c12; border: none; border-radius: 5px; color: white; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Arsiv ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterFilms()"><option value="">Tum Turler</option></select>
            <input type="text" id="searchInput" placeholder="Ara..." oninput="filterFilms()">
        </div>
    </div>
    
    <div class="film-container" id="filmContainer"></div>
    <button id="loadMore" onclick="loadMoreFilms()">Daha Fazla</button>

    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="mTitle"></h2>
            <div id="mMeta"></div>
            <p id="mSummary" style="color: #ccc; line-height: 1.5;"></p>
            <a id="mWatch" class="btn-watch" target="_blank">IZLE</a>
        </div>
    </div>

    <script>
        const films = {films_json};
        const allGenres = {genres_json};
        let currentPage = 1;
        const perPage = 24;
        let list = films;

        const sel = document.getElementById('genreSelect');
        allGenres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g; opt.innerText = g; sel.appendChild(opt);
        }});

        function createCard(f) {{
            const d = document.createElement('div');
            d.className = 'film-card';
            d.innerHTML = `<img src="${{f.image}}" loading="lazy"><div class="film-title">${{f.title}}</div>`;
            d.onclick = () => openModal(f);
            return d;
        }}

        function render() {{
            const c = document.getElementById('filmContainer');
            if(currentPage===1) c.innerHTML='';
            
            const start = (currentPage-1)*perPage;
            const end = start+perPage;
            const batch = list.slice(start, end);
            
            batch.forEach(f => c.appendChild(createCard(f)));
            document.getElementById('loadMore').style.display = end>=list.length ? 'none' : 'block';
        }}

        function loadMoreFilms() {{ currentPage++; render(); }}

        function filterFilms() {{
            const s = document.getElementById('searchInput').value.toLowerCase();
            const g = document.getElementById('genreSelect').value;
            list = films.filter(f => (f.title.toLowerCase().includes(s)) && (g==="" || f.genres.includes(g)));
            currentPage=1; render();
        }}

        function openModal(f) {{
            document.getElementById('mTitle').innerText = f.title;
            document.getElementById('mSummary').innerText = f.summary || "Ozet yok.";
            let h = `<span class="meta-tag">${{f.year}}</span><span class="meta-tag">IMDB: ${{f.imdb}}</span><span class="meta-tag">${{f.duration}}</span>`;
            if(f.genres) f.genres.forEach(g => h+=`<span class="meta-tag" style="background:#e67e22">${{g}}</span>`);
            document.getElementById('mMeta').innerHTML = h;
            document.getElementById('mWatch').href = f.videoUrl || f.url;
            document.getElementById('filmModal').style.display = 'block';
        }}

        function closeModal() {{ document.getElementById('filmModal').style.display='none'; }}
        window.onclick = (e) => {{ if(e.target == document.getElementById('filmModal')) closeModal(); }}
        
        render();
    </script>
</body>
</html>"""
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False)

if __name__ == "__main__":
    data = get_all_films()
    if data:
        create_html(data)
