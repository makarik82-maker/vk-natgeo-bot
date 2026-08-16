import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

BASE = "https://api.vkvideo.ru/method/"
COMMON = {"v": "5.285", "client_id": "52461373", "lang": "0", "https": "1"}

OWNER = "-233780972"  # владелец, взят из URL плейлистов

def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://vkvideo.ru",
        "Referer": "https://vkvideo.ru/",
    })

    r = s.get("https://login.vk.ru/?act=get_anonym_token", timeout=30)
    print("[anonym] status:", r.status_code)
    print(r.text[:500])
    token = ""
    try:
        data = r.json()
        token = data.get("response", {}).get("token", "") or data.get("token", "")
    except Exception as e:
        print("parse error:", e)
    if not token:
        token = r.text.strip()
    print("token:", token[:60])

    def call(method, **params):
        p = dict(COMMON)
        p["access_token"] = token
        p.update(params)
        try:
            rr = s.get(BASE + method, params=p, timeout=30)
            print(f"\n=== {method} === status {rr.status_code}")
            print(rr.text[:1500])
        except Exception as e:
            print(f"[{method}] error:", e)

    call("utils.resolveScreenName", screen_name="natgeostream")
    call("video.getPlaylists", owner_id=OWNER, count="100", offset="0")
    call("video.getAlbums", owner_id=OWNER, count="100", offset="0")
    call("playlists.get", owner_id=OWNER, count="100")
    call("video.get", owner_id=OWNER, album_id="136", count="20")
    call("playlists.getVideos", playlist_id=f"{OWNER}_136", count="20")

if __name__ == "__main__":
    main()
