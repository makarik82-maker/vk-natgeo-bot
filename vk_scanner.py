import json
import os
import re
import requests

OWNER_ID = "-233780972"            # natgeostream
COMMON = {"v": "5.285", "client_id": "52461373", "lang": "0", "https": "1"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9",
           "Origin": "https://vkvideo.ru", "Referer": "https://vkvideo.ru/"}
STATE_FILE = "state.json"

def get_token(s):
    r = s.get("https://login.vk.ru/?act=get_anonym_token",
              params={"client_id": "52461373"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("type") != "okay":
        raise RuntimeError(f"token error: {data}")
    return data["data"]["access_token"]

def api_call(s, method, token, **params):
    p = dict(COMMON)
    p["access_token"] = token
    p.update(params)
    r = s.get(f"https://api.vkvideo.ru/method/{method}", params=p, timeout=30)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"API {method}: {body['error']}")
    return body.get("response")

def get_playlist_description(s, owner_id, album_id):
    url = f"https://vkvideo.ru/playlist/{owner_id}_{album_id}"
    try:
        r = s.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
                      r.text)
        if not m:
            m = re.search(r'<meta[^>]+content="([^"]*)"[^>]+property="og:description"',
                          r.text)
        if m:
            desc = m.group(1).strip()
            # 2-3 предложения: разбиваем по точке/воскл/вопр, берём первые 3
            sentences = re.split(r'(?<=[.!?])\s+', desc)
            return " ".join(sentences[:3]).strip()
    except Exception as e:
        print(f"[warn] desc fetch failed for {url}: {e}")
    return ""

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"playlist_index": 0, "video_index": 0}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(text):
    token = os.environ["BOT_TOKEN"]
    chat_id = os.environ["CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=30)
    print("Telegram:", r.status_code, r.text[:300])
    r.raise_for_status()

def main():
    s = requests.Session()
    s.headers.update(HEADERS)

    token = get_token(s)
    print("token OK")

    # 1. Все плейлисты
    albums_resp = api_call(s, "video.getAlbums", token,
                           owner_id=OWNER_ID, count="100")
    albums = albums_resp.get("items", []) if isinstance(albums_resp, dict) else []
    print(f"playlists: {len(albums)}")
    if not albums:
        print("no playlists, exit")
        return

    state = load_state()
    p_idx = state.get("playlist_index", 0) % len(albums)

    # 2. Сколько видео в текущем плейлисте
    album = albums[p_idx]
    album_id = album["id"]
    album_title = album.get("title", "Без названия").strip()
    total_in_album = int(album.get("count", 0))
    print(f"current: #{p_idx} '{album_title}', videos={total_in_album}")

    # Если плейлист пустой или видео кончились — переходим к следующему
    if total_in_album == 0 or state.get("video_index", 0) >= total_in_album:
        p_idx = (p_idx + 1) % len(albums)
        album = albums[p_idx]
        album_id = album["id"]
        album_title = album.get("title", "Без названия").strip()
        total_in_album = int(album.get("count", 0))
        v_idx = 0
        print(f"-> next playlist #{p_idx} '{album_title}', videos={total_in_album}")
    else:
        v_idx = state.get("video_index", 0)

    # 3. Описание с веб-страницы
    desc = get_playlist_description(s, OWNER_ID, album_id)
    if not desc:
        desc = "Документальный сериал National Geographic."

    # 4. Формируем и отправляем пост
    playlist_url = f"https://vkvideo.ru/playlist/{OWNER_ID}_{album_id}"
    post = (
        f"🎬 <b>{album_title}</b>\n\n"
        f"{desc}\n\n"
        f'🔗 <a href="{playlist_url}">Плейлист</a>'
    )
    print("\n--- POST ---")
    print(post)
    print("------------\n")
    send_telegram(post)

    # 5. Обновляем состояние
    v_idx += 1
    if v_idx >= total_in_album:
        # Плейлист исчерпан — в следующий раз перейдём к следующему
        p_idx = (p_idx + 1) % len(albums)
        v_idx = 0
    save_state({"playlist_index": p_idx, "video_index": v_idx})
    print(f"state saved: playlist={p_idx}, video={v_idx}")

if __name__ == "__main__":
    main()
