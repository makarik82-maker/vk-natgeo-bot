import json
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

COMMON = {"v": "5.285", "client_id": "52461373", "lang": "0", "https": "1"}
OWNER_ID = "-233780972"  # natgeostream — из URL плейлистов

def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://vkvideo.ru",
        "Referer": "https://vkvideo.ru/",
    })

    # 1. Токен
    print("=== GET ANONYM TOKEN ===")
    r = s.get("https://login.vk.ru/?act=get_anonym_token",
              params={"client_id": "52461373"}, timeout=30)
    print(f"status: {r.status_code}")
    data = r.json()
    print(f"response: {json.dumps(data, indent=2, ensure_ascii=False)[:800]}")

    if data.get("type") != "okay":
        print("ERROR: unexpected token response")
        return
    token = data["data"]["access_token"]
    print(f"OK token: {token[:60]}...")

    # 2. Плейлисты (альбомы)
    print("\n=== GET ALBUMS ===")
    p = dict(COMMON)
    p["access_token"] = token
    p["owner_id"] = OWNER_ID
    p["count"] = "100"
    r = s.get("https://api.vkvideo.ru/method/video.getAlbums",
              params=p, timeout=30)
    print(f"status: {r.status_code}")
    albums = r.json()
    print(f"top keys: {list(albums.keys())}")

    if "response" not in albums:
        print(f"ERROR: {json.dumps(albums, ensure_ascii=False)[:500]}")
        return

    resp = albums["response"]
    print(f"resp keys: {list(resp.keys()) if isinstance(resp, dict) else type(resp)}")
    items = resp.get("items", []) if isinstance(resp, dict) else []
    total = resp.get("count", "?") if isinstance(resp, dict) else "?"
    print(f"count={total}, items={len(items)}")

    if items:
        print("\n--- FIRST ALBUM FULL ---")
        print(json.dumps(items[0], indent=2, ensure_ascii=False))

    # 3. Видео из первого альбома
    if items:
        album_id = items[0]["id"]
        print(f"\n=== GET VIDEOS FROM ALBUM {album_id} ===")
        p2 = dict(COMMON)
        p2["access_token"] = token
        p2["owner_id"] = OWNER_ID
        p2["album_id"] = str(album_id)
        p2["count"] = "100"
        r = s.get("https://api.vkvideo.ru/method/video.get",
                  params=p2, timeout=30)
        print(f"status: {r.status_code}")
        vids = r.json()
        print(f"top keys: {list(vids.keys())}")
        if "response" in vids:
            vr = vids["response"]
            vitems = vr.get("items", []) if isinstance(vr, dict) else []
            print(f"count={vr.get('count','?')}, items={len(vitems)}")
            if vitems:
                print("\n--- FIRST VIDEO FULL ---")
                print(json.dumps(vitems[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
