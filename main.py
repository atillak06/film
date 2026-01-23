import cloudscraper
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

def get_scraper():
    """Bot korumasını aşan özel tarayıcı."""
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def get_movie_details(scraper, movie_url):
    """
    Filmin detay sayfasına girer; 
    Video Linki, Özet, Türler, Süre vb. detayları çeker.
    """
    info = {
        'videoUrl': movie_url, # Bulamazsa sayfa linkini koyar
        'summary': 'Özet bulunamadı.',
        'genres': ['Genel'],
        'duration': 'Belirtilmemiş'
    }
    
    try:
        response = scraper.get(movie_url, timeout=10)
        if response.status_code != 200:
            return info
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Video Linki (Iframe)
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            info['videoUrl'] = iframe['src']
            
        # 2. Özet (Genelde 'ozet-text' veya 'summary' class'ında olur)
        summary_el = soup.select_one('.ozet-text') or soup.select_one('.summary') or soup.find('article')
        if summary_el:
            info['summary'] = html.unescape(summary_el.text.strip())
            
        # 3. Türler (Genelde 'tur' veya 'genres' class'ında linkler olur)
        genre_links = soup.select('.tur a') or soup.select('.genres a')
        if genre_links:
            info['genres'] = [html.unescape(g.text.strip()) for g in genre_links]
            
        # 4. Süre
        duration_el = soup.select_one('.sure') or soup.select_one('.duration')
        if duration_el:
            info['duration'] = html.unescape(duration_el.text.strip())
            
        return info

    except Exception as e:
        print(f"Detay çekilemedi ({movie_url}): {e}")
        return info

def parse_films_from_list(soup, base_domain):
    """Listeden temel bilgileri alır."""
    films = []
    # Site yapısına göre elementleri seç
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

            # Başlık
            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "İsimsiz"

            # Resim
            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            # Yıl ve IMDB
            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            if title != "İsimsiz" and "dizipal" in full_url:
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
    scraper = get_scraper()
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tasarım Modu Başlatılıyor: {BASE_URL}")
    print("Her filmin detayları (Özet, Tür, Video) çekilecek. Bu işlem uzun sürebilir.")
    print("------------------------------------------------")

    # --- 1. SAYFA ---
    try:
        response = scraper.get(BASE_URL, timeout=30)
        if response.status_code != 200:
            print("Siteye girilemedi.")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        new_films = parse_films_from_list(soup, base_domain)
        
        for f in new_films:
            if f['title'] not in processed_titles:
                print(f">> Detaylar alınıyor: {f['title']}")
                # Detay sayfasına git ve eksikleri tamamla
                details = get_movie_details(scraper, f['url'])
                f.update(details) # Film verisine detayları ekle
                
                all_films.append(f)
                processed_titles.add(f['title'])
                time.sleep(0.2) 
                
        print(f"Sayfa 1 Tamam. ({len(all_films)} Film)")
        
    except Exception as e:
        print(f"Kritik Hata: {e}")
        return []

    # --- 2. API DONGUSU (SONSUZ KAYDIRMA) ---
    page = 1
    MAX_PAGES = 50 # İstersen artırabilirsin
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id: break
            
        print(f"Sıradaki sayfa çekiliyor (Ref: {last_id})...")
        
        try:
            payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
            response = scraper.post(api_url, data=payload, timeout=20)
            
            try:
                data = response.json()
            except:
                break
                
            if not data or not data.get('html'):
                break
                
            html_part = BeautifulSoup(data['html'], 'html.parser')
            more_films = parse_films_from_list(html_part, base_domain)
            
            added_count = 0
            for f in more_films:
                if f['title'] not in processed_titles:
                    # Detayları çek
                    details = get_movie_details(scraper, f['url'])
                    f.update(details)
                    
                    all_films.append(f)
                    processed_titles.add(f['title'])
                    added_count += 1
                    time.sleep(0.2)
            
            if added_count == 0:
                print("Yeni film yok. Bitti.")
                break
                
            page += 1
            print(f"--- Sayfa {page} Tamamlandı. Toplam: {len(all_films)} ---")
            
        except Exception as e:
            print(f"Döngü hatası: {e}")
            break

    return all_films

def get_all_genres(films):
    """Tüm filmlerden benzersiz türlerin bir listesini oluşturur."""
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
    """Senin istediğin özel tasarımlı HTML dosyasını oluşturur."""
    
    # Python verisini Javascript'e uygun formata çevir
    films_json = json.dumps(films, ensure_ascii=False)
    all_genres = get_all_genres(films)
    genres_json = json.dumps(all_genres, ensure_ascii=False)
    
    # SENİN İSTEDİĞİN HTML ŞABLONU (Dinamik verilerle)
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Film İzle</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #344966; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #2c3e50; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        h1 {{ margin: 0; color: #ecf0f1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 1.5em; }}
        .controls {{ display: flex; align-items: center; }}
        .search-container {{ position: relative; transition: width 0.3s; width: 40px; height: 40px; overflow: hidden; }}
        .search-container.active {{ width: 200px; }}
        #searchInput {{ padding: 5px 40px 5px 15px; width: 100%; height: 100%; box-sizing: border-box; border: none; border-radius: 20px; background-color: #496785; color: #fff; outline: none; }}
        #searchInput::placeholder {{ color: #bdc3c7; transition: opacity 0.3s; }}
        .search-container:not(.active) #searchInput::placeholder {{ opacity: 0; }}
        .search-icon {{ position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: #bdc3c7; cursor: pointer; }}
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; margin-top: 80px; padding: 20px; }}
        .film-card {{ position: relative; overflow: hidden; border-radius: 8px; background-color: #496785; box-shadow: 0 4px 8px rgba(0,0,0,0.3); transition: transform 0.2s ease; }}
        .film-card:hover {{ transform: translateY(-5px); }}
        .film-card img {{ width: 100%; display: block; aspect-ratio: 2 / 3; object-fit: cover; }}
        .film-overlay {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(44, 62, 80, 0.95), rgba(44, 62, 80, 0)); padding: 20px 10px 10px; transform: translateY(100%); transition: transform 0.3s ease; }}
        .film-card:hover .film-overlay {{ transform: translateY(0); }}
        .film-title {{ font-weight: bold; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #ecf0f1; }}
        .film-buttons {{ display: flex; justify-content: space-between; margin-top: 10px; }}
        .btn {{ padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8em; text-decoration: none; color: #fff; display: inline-block; text-align: center; }}
        .btn-info {{ background-color: #f39c12; }}
        .btn-watch {{ background-color: #3498db; }}
        #loadMore {{ display: block; width: 200px; margin: 20px auto; padding: 12px; background-color: #f39c12; color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; }}
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(5px); }}
        .modal-content {{ background-color: #496785; margin: 10% auto; padding: 25px; border-radius: 8px; width: 90%; max-width: 600px; color: #ecf0f1; position: relative; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }}
        .close {{ color: #bdc3c7; position: absolute; top: 10px; right: 20px; font-size: 28px; font-weight: bold; cursor: pointer; }}
        .close:hover {{ color: #fff; }}
        #modalTitle {{ margin-top: 0; }}
        #modalWatchBtn {{ position: absolute; bottom: 25px; right: 25px; background-color: #3498db; color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }}
        #genreSelect {{ margin-right: 10px; padding: 8px; border-radius: 5px; background-color: #496785; color: #fff; border: 1px solid #2c3e50; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Film Arşivi ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterByGenre(this.value)">
                <option value="">Tüm Türler</option>
            </select>
            <div class="search-container" id="searchContainer">
                <input type="text" id="searchInput" placeholder="Film ara..." oninput="searchFilms()">
                <span class="search-icon" onclick="toggleSearch()">🔍</span>
            </div>
        </div>
    </div>
    <div class="film-container" id="filmContainer"></div>
    <button id="loadMore" onclick="loadMoreFilms()">Daha Fazla Yükle</button>
    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="modalTitle"></h2>
            <p id="modalYear"></p>
            <p id="modalImdb"></p>
            <p id="modalDuration"></p>
            <p id="modalGenres"></p>
            <p id="modalSummary"></p>
            <a id="modalWatchBtn" class="btn btn-watch" target="_blank">İzle</a>
        </div>
    </div>
    <script>
        const films = {films_json};
        const allGenres = {genres_json};
        let currentPage = 1;
        const filmsPerPage = 24;
        let currentFilter = {{ "genre": "", "search": "" }};

        function populateGenreSelect() {{
            const select = document.getElementById('genreSelect');
            allGenres.forEach(genre => {{
                const option = document.createElement('option');
                option.value = genre;
                option.textContent = genre;
                select.appendChild(option);
            }});
        }}

        function getFilteredFilms() {{
            return films.filter(film => {{
                const matchesGenre = currentFilter.genre ? film.genres.includes(currentFilter.genre) : true;
                const searchLower = currentFilter.search.toLowerCase();
                const matchesSearch = currentFilter.search ? 
                    film.title.toLowerCase().includes(searchLower) || 
                    film.genres.join(',').toLowerCase().includes(searchLower) : true;
                return matchesGenre && matchesSearch;
            }});
        }}

        function renderFilms() {{
            const container = document.getElementById('filmContainer');
            container.innerHTML = '';
            currentPage = 1;
            const filteredFilms = getFilteredFilms();

            const filmsToRender = filteredFilms.slice(0, filmsPerPage);
            filmsToRender.forEach(film => container.appendChild(createFilmCard(film)));

            document.getElementById('loadMore').style.display = filteredFilms.length > filmsPerPage ? 'block' : 'none';
        }}
        
        function createFilmCard(film) {{
            const filmCard = document.createElement('div');
            filmCard.className = 'film-card';
            const filmTitle = film.title.replace(/'/g, "\\'");
            filmCard.innerHTML = `
                <img src="${{film.image}}" alt="${{filmTitle}}" loading="lazy">
                <div class="film-overlay">
                    <div class="film-title">${{film.title}}</div>
                    <div class="film-buttons">
                        <button class="btn btn-info" onclick='event.stopPropagation(); showDetails("${{filmTitle}}")'>Bilgi</button>
                        <a href="${{film.videoUrl}}" class="btn btn-watch" target="_blank" onclick='event.stopPropagation();'>İzle</a>
                    </div>
                </div>
            `;
            filmCard.onclick = () => showDetails(film.title);
            return filmCard;
        }}

        function searchFilms() {{
            currentFilter.search = document.getElementById('searchInput').value;
            renderFilms();
        }}

        function filterByGenre(genre) {{
            currentFilter.genre = genre;
            renderFilms();
        }}

        function showDetails(title) {{
            const film = films.find(f => f.title === title);
            if (film) {{
                document.getElementById('modalTitle').textContent = film.title;
                document.getElementById('modalYear').textContent = 'Yıl: ' + film.year;
                document.getElementById('modalImdb').textContent = 'IMDB: ' + film.imdb;
                document.getElementById('modalDuration').textContent = 'Süre: ' + film.duration;
                document.getElementById('modalGenres').textContent = 'Türler: ' + film.genres.join(', ');
                document.getElementById('modalSummary').textContent = film.summary;
                document.getElementById('modalWatchBtn').href = film.videoUrl;
                document.getElementById('filmModal').style.display = 'block';
            }}
        }}

        function closeModal() {{
            document.getElementById('filmModal').style.display = 'none';
        }}

        window.onclick = function(event) {{
            const modal = document.getElementById('filmModal');
            if (event.target == modal) {{
                modal.style.display = "none";
            }}
        }}

        function loadMoreFilms() {{
            const filteredFilms = getFilteredFilms();
            const startIndex = currentPage * filmsPerPage;
            const endIndex = startIndex + filmsPerPage;
            
            const filmsToRender = filteredFilms.slice(startIndex, endIndex);
            const container = document.getElementById('filmContainer');
            filmsToRender.forEach(film => container.appendChild(createFilmCard(film)));

            currentPage++;
            if (endIndex >= filteredFilms.length) {{
                document.getElementById('loadMore').style.display = 'none';
            }}
        }}

        function toggleSearch() {{
            const searchContainer = document.getElementById('searchContainer');
            searchContainer.classList.toggle('active');
            if (searchContainer.classList.contains('active')) {{
                document.getElementById('searchInput').focus();
            }}
        }}

        // Initial Load
        document.addEventListener("DOMContentLoaded", () => {{
            populateGenreSelect();
            renderFilms();
        }});
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
    else:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write("<h1>Hata: Film verileri alınamadı.</h1>")
