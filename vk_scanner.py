import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://vkvideo.ru",
        "Referer": "https://vkvideo.ru/",
    })

    print("=== ЧАСТЬ A: подбор параметров токена ===")
    combos = [
        {"client_id": "52461373"},
        {"client_id": "52461373", "scope": "0"},
        {"client_id": "52461373", "v": "5.285"},
        {"client_id": "52461373", "grant_type": "client_credentials"},
    ]
    for params in combos:
        try:
            rr = s.get("https://login.vk.ru/?act=get_anonym_token",
                       params=params, timeout=30)
            print("GET", params, "->", rr.status_code, rr.text[:100])
        except Exception as e:
            print("GET", params, "error", e)

    for method in ("video.getAlbums", "video.get"):
        p = {"v": "5.285", "client_id": "52461373",
             "owner_id": "-233780972", "count": "5"}
        if method == "video.get":
            p["album_id"] = "136"
        rr = s.get("https://api.vkvideo.ru/method/" + method,
                   params=p, timeout=30)
        print(f"\n[{method} без токена]", rr.status_code, rr.text[:200])

    print("\n=== ЧАСТЬ B: археология JS ===")
    r = s.get("https://vkvideo.ru/", timeout=30)
    scripts = [u for u in re.findall(r'<script[^>]+src="([^"]+)"', r.text)
               if ".js" in u]
    print("script bundles:", len(scripts))
    hits = []
    for url in scripts[:20]:
        if url.startswith("/"):
            url = "https://vkvideo.ru" + url
        try:
            js = s.get(url, timeout=30).text
        except Exception as e:
            print("err", e)
            continue
        print(url.split("/")[-1], len(js))
        for marker in ("get_anonym_token", "anonym_token", "getAlbums", "album_id"):
            for m in re.finditer(marker, js):
                a = max(0, m.start() - 250)
                b = min(len(js), m.end() + 250)
                hits.append((url.split("/")[-1], marker, js[a:b]))

    print("\nHITS:", len(hits))
    for name, marker, snippet in hits[:25]:
        print(f"\n--- {name} / {marker} ---")
        print(snippet)

if __name__ == "__main__":
    main()
