import requests
from bs4 import BeautifulSoup
import json
import os
import time
import html
import re  # Temizlik icin gerekli
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_soup(url, method='GET', data=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': BASE_URL,
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=data, timeout=20)
        else:
            response = requests.get(url, headers=headers, timeout=20)
            
        if response.status_code != 200: return None
        if method == 'POST':
            try: return response.json()
            except: return None
        return BeautifulSoup(response.content, 'html.parser')
    except:
        return None

def clean_summary_text(text):
    """
    Özet içindeki 'Full izle', 'HD izle' gibi çöp (SEO) metinleri temizler.
    Sadece gerçek cümleleri bırakır.
    """
    if not text: return "Özet bilgisi henüz eklenmemiş."
    
    # İstenmeyen kelimeler listesi (Küçük harf)
    spam_keywords = [
        "full izle", "hd izle", "türkçe dublaj", "altyazılı izle", 
        "tek parça", "donmadan izle", "filmini izle", "indir", "film izle",
        "cinemaximum", "netflix", "vizyon tarihi"
    ]
    
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        line_lower = line.lower().strip()
        # Eğer satır spam kelimeler içeriyorsa ve çok kısaysa (gerçek cümle değilse) atla
        is_spam = False
        for spam in spam_keywords:
            if spam in line_lower:
                is_spam = True
                break
        
        # Eğer spam değilse veya spam kelime geçse bile uzun bir cümle ise (gerçek özet olabilir) al
        if not is_spam or len(line) > 150:
            clean_lines.append(line.strip())
            
    result = " ".join(clean_lines)
    
    # Parantez içindeki (2024) (Full İzle) gibi şeyleri temizle
    result = re.sub(r'\((.*?)(izle|dublaj|altyazı|film)(.*?)\)', '', result, flags=re.IGNORECASE)
    
    # Eğer temizlik sonrası eldekiler çok kısaysa
    if len(result) < 10:
        return "Bu filmin özeti otomatik metin içerdiği için temizlendi."
        
    return result

def get_movie_details(movie_url):
    info = {
        'videoUrl': movie_url,
        'summary': 'Özet yok.',
        'genres': [],
        'duration': '',
        'imdb': '',
        'year': ''
    }
    
    soup = get_soup(movie_url)
    if not soup: return info

    try:
        # 1. Video Linki
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            info['videoUrl'] = iframe['src']
            
        # 2. Özet (Daha akıllı seçim ve TEMİZLİK)
        # Genelde gerçek özet <p> etiketindedir, spamlar <h1> veya <div> dedir.
        summary_container = soup.select_one('.ozet-text') or soup.select_one('.film-ozeti') or soup.select_one('.summary') or soup.find('article')
        
        if summary_container:
            # Varsa sadece <p> etiketlerini al, yoksa hepsini al
            paragraphs = summary_container.find_all('p')
            if paragraphs:
                raw_text = " ".join([p.text for p in paragraphs])
            else:
                raw_text = summary_container.text
            
            # Temizlik fonksiyonuna gönder
            info['summary'] = clean_summary_text(raw_text)
            
        # 3. KATEGORİLER (Daha geniş arama)
        # Sitedeki olası tüm kategori sınıflarını dene
        genre_links = []
        possible_selectors = [
            '.tur a', '.genres a', '.category a', '.film-meta a[href*="tur"]', 
            '.film-meta a[href*="genre"]', '.tags a', '.film-content a'
        ]
        
        for selector in possible_selectors:
            found = soup.select(selector)
            if found:
                genre_links.extend(found)
        
        # Benzersizleri al ve temizle
        if genre_links:
            unique_genres = set()
            for g in genre_links:
                txt = html.unescape(g.text.strip())
                # "2024", "ABD" gibi kategori olmayanları filtrele
                if txt and not txt.isdigit() and len(txt) > 2 and "Film" not in txt:
                    unique_genres.add(txt)
            info['genres'] = list(unique_genres)
            
        # 4. Süre
        duration_el = soup.select_one('.sure') or soup.select_one('.duration') or soup.select_one('.time')
        if duration_el: info['duration'] = html.unescape(duration_el.text.strip())
            
        # 5. IMDB ve Yıl
        imdb_el = soup.select_one('.imdb') or soup.select_one('.puan')
        if imdb_el: info['imdb'] = imdb_el.text.strip()
        
        year_el = soup.select_one('.vizyon-tarihi') or soup.select_one('.year')
        if year_el: info['year'] = year_el.text.strip()

    except Exception as e:
        print(f"Detay hatasi: {e}")
        
    return info

def parse_films_from_list(soup, base_domain):
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
            title = title_el.text.strip() if title_el else "İsimsiz"
            
            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            if title != "İsimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": html.unescape(title),
                    "image": image,
                    "url": full_url
                })
        except:
            continue
    return films

def get_all_films():
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"TARAMA BAŞLIYOR: {BASE_URL}")
    
    # 1. SAYFA
    soup = get_soup(BASE_URL)
    if not soup: return []

    new_films = parse_films_from_list(soup, base_domain)
    
    for f in new_films:
        if f['title'] not in processed_titles:
            print(f">> İşleniyor: {f['title']}")
            details = get_movie_details(f['url'])
            f.update(details)
            all_films.append(f)
            processed_titles.add(f['title'])
            time.sleep(0.1) 
            
    print(f"Sayfa 1 Bitti. ({len(all_films)} Film)")

    # 2. DÖNGÜ (SONSUZ)
    page = 1
    MAX_PAGES = 5000 
    
    while page < MAX_PAGES:
        if not all_films: break
        last_film = all_films[-1]
        last_id = last_film.get('id')
        if not last_id: break
            
        print(f"Sıradaki sayfa... (Ref: {last_id})")
        payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
        data = get_soup(api_url, method='POST', data=payload)
        
        if not data or not data.get('html'): break
            
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
                time.sleep(0.1)
        
        if added_count == 0: break
        page += 1
        print(f"Sayfa {page} Tamam. Toplam: {len(all_films)}")

    return all_films

def get_all_genres(films):
    # Türleri otomatik topla
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre: all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
    all_genres = get_all_genres(films)
    films_json = json.dumps(films, ensure_ascii=False)
    genres_json = json.dumps(all_genres, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dizipal Arşiv</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 0; background-color: #1a1a1a; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #0f0f0f; padding: 15px; display: flex; flex-direction: column; align-items: center; z-index: 1000; box-shadow: 0 5px 20px rgba(0,0,0,0.5); }}
        h1 {{ margin: 0 0 10px 0; font-size: 1.5em; color: #e50914; text-transform: uppercase; letter-spacing: 2px; }}
        .controls {{ display: flex; gap: 10px; width: 100%; max-width: 600px; justify-content: center; }}
        select, input {{ padding: 12px; border-radius: 6px; border: 1px solid #333; background: #222; color: #eee; font-size: 16px; }}
        input {{ flex-grow: 1; }}
        
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; margin-top: 120px; padding: 20px; }}
        .film-card {{ border-radius: 8px; background: #222; overflow: hidden; cursor: pointer; transition: transform 0.2s; position: relative; }}
        .film-card:hover {{ transform: scale(1.05); z-index: 10; box-shadow: 0 0 15px rgba(229, 9, 20, 0.4); }}
        .film-card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        
        .film-overlay {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.95), transparent); padding: 15px 10px; }}
        .film-title {{ text-align: center; font-size: 0.9em; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); backdrop-filter: blur(8px); }}
        .modal-content {{ background: #1a1a1a; margin: 5% auto; padding: 30px; width: 90%; max-width: 600px; border-radius: 12px; position: relative; border: 1px solid #333; }}
        .close {{ position: absolute; top: 15px; right: 20px; font-size: 35px; cursor: pointer; color: #888; transition: color 0.3s; }}
        .close:hover {{ color: #fff; }}
        
        #mTitle {{ color: #e50914; margin-top: 0; }}
        .btn-watch {{ display: block; width: 100%; background: #e50914; color: white; text-align: center; padding: 15px; border-radius: 8px; text-decoration: none; margin-top: 25px; font-weight: bold; font-size: 1.2em; }}
        .btn-watch:hover {{ background: #b20710; }}
        
        .tag {{ display: inline-block; background: #333; padding: 5px 10px; border-radius: 4px; font-size: 0.85em; margin: 0 5px 5px 0; color: #ccc; }}
        .tag-genre {{ background: #e50914; color: #fff; }}
        
        #loadMore {{ display: block; margin: 40px auto; padding: 15px 50px; background: #333; border: 1px solid #444; border-radius: 8px; color: white; cursor: pointer; font-size: 1.1em; }}
        #loadMore:hover {{ background: #444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ARŞİV ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterFilms()"><option value="">Tüm Türler</option></select>
            <input type="text" id="searchInput" placeholder="Film Ara..." oninput="filterFilms()">
        </div>
    </div>
    
    <div class="film-container" id="filmContainer"></div>
    <button id="loadMore" onclick="loadMoreFilms()">DAHA FAZLA YÜKLE</button>

    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="mTitle"></h2>
            <div id="mMeta"></div>
            <p id="mSummary" style="color: #bbb; line-height: 1.6; margin-top: 20px;"></p>
            <a id="mWatch" class="btn-watch" target="_blank">🎬 FİLMİ İZLE</a>
        </div>
    </div>

    <script>
        const films = {films_json};
        const allGenres = {genres_json};
        let currentPage = 1;
        const perPage = 30;
        let list = films;

        const sel = document.getElementById('genreSelect');
        allGenres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g; opt.innerText = g; sel.appendChild(opt);
        }});

        function createCard(f) {{
            const d = document.createElement('div');
            d.className = 'film-card';
            d.innerHTML = `<img src="${{f.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300?text=Resim+Yok'"><div class="film-overlay"><div class="film-title">${{f.title}}</div></div>`;
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
            list = films.filter(f => {{
                const hasGenre = g === "" || (f.genres && f.genres.includes(g));
                const matchesSearch = f.title.toLowerCase().includes(s);
                return hasGenre && matchesSearch;
            }});
            currentPage=1; render();
        }}

        function openModal(f) {{
            document.getElementById('mTitle').innerText = f.title;
            document.getElementById('mSummary').innerText = f.summary;
            
            let h = '';
            if(f.year) h += `<span class="tag">${{f.year}}</span>`;
            if(f.imdb) h += `<span class="tag">IMDB: ${{f.imdb}}</span>`;
            if(f.duration) h += `<span class="tag">${{f.duration}}</span>`;
            if(f.genres) f.genres.forEach(g => h+=`<span class="tag tag-genre">${{g}}</span>`);
            
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
