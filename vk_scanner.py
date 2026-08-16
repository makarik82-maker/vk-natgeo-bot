import re
import requests

CHANNEL_URL = "https://vkvideo.ru/@natgeostream/playlists"
MOBILE_URL = "https://m.vkvideo.ru/@natgeostream/playlists"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

PLAYLIST_RE = re.compile(r"/playlist/(-?\d+_\d+)")

def fetch(url):
    print(f"[GET] {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    print(f"    status={r.status_code}, size={len(r.text)} bytes")
    return r.text

def extract_playlist_ids(html):
    ids = []
    for m in PLAYLIST_RE.finditer(html):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids

def get_meta(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % prop, html)
    if not m:
        m = re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % prop, html)
    return m.group(1) if m else ""

def main():
    html = None
    for url in (CHANNEL_URL, MOBILE_URL):
        try:
            html = fetch(url)
            if len(html) > 1000:
                break
        except Exception as e:
            print("    error:", e)

    if not html:
        print("FAIL: не удалось загрузить страницу канала")
        return

    ids = extract_playlist_ids(html)
    print(f"\nНайдено уникальных плейлистов: {len(ids)}")

    for pid in ids:
        purl = f"https://vkvideo.ru/playlist/{pid}"
        try:
            phtml = fetch(purl)
            title = get_meta(phtml, "og:title")
            desc = get_meta(phtml, "og:description") or get_meta(phtml, "description")
            print(f"\n=== PLAYLIST {pid} ===")
            print("TITLE:", title)
            print("DESC :", desc[:300])
        except Exception as e:
            print("    error:", e)

if __name__ == "__main__":
    main()
