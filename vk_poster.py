import json
import os
import re
import ssl
import requests
import urllib3

# Отключаем предупреждения о самоподписанных сертификатах GigaChat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

def get_gigachat_description(playlist_title):
    """Генерирует описание через GigaChat API"""
    credentials = os.environ.get("GIGACHAT_CREDENTIALS")
    if not credentials:
        print("[gigachat] credentials not found, using fallback")
        return None
    
    try:
        # 1. Получаем access token
        token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": "00000000-0000-0000-0000-000000000001",
            "Authorization": credentials
        }
        token_data = {"scope": "GIGACHAT_API_PERS"}
        
        print("[gigachat] requesting token...")
        token_resp = requests.post(
            token_url,
            headers=token_headers,
            data=token_data,
            verify=False,  # GigaChat использует самоподписанные сертификаты
            timeout=30
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        
        if not access_token:
            print("[gigachat] no access token in response")
            return None
        
        # 2. Генерируем описание
        chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        chat_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        prompt = (
            f"Напиши краткое описание (2-3 предложения) для документального сериала "
            f"'{playlist_title}' от National Geographic. "
            f"Описание должно быть увлекательным и информативным."
        )
        
        chat_payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        print("[gigachat] generating description...")
        chat_resp = requests.post(
            chat_url,
            headers=chat_headers,
            json=chat_payload,
            verify=False,
            timeout=30
        )
        chat_resp.raise_for_status()
        
        choices = chat_resp.json().get("choices", [])
        if choices:
            description = choices[0].get("message", {}).get("content", "").strip()
            print(f"[gigachat] generated: {description[:100]}...")
            return description
        
        print("[gigachat] no choices in response")
        return None
        
    except Exception as e:
        print(f"[gigachat] error: {e}")
        return None

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"playlist_index": 0}
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

    # 2. Текущий плейлист
    album = albums[p_idx]
    album_id = album["id"]
    album_title = album.get("title", "Без названия").strip()
    print(f"current: #{p_idx} '{album_title}'")

    # 3. Генерируем описание через GigaChat (или fallback)
    desc = get_gigachat_description(album_title)
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

    # 5. Переход к следующему плейлисту (цикл)
    p_idx = (p_idx + 1) % len(albums)
    save_state({"playlist_index": p_idx})
    print(f"state saved: next playlist={p_idx}")

if __name__ == "__main__":
    main()
