import json
import os
import re
import uuid
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OWNER_ID = "-233780972"
COMMON = {"v": "5.285", "client_id": "52461373", "lang": "0", "https": "1"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9",
           "Origin": "https://vkvideo.ru", "Referer": "https://vkvideo.ru/"}
STATE_FILE = "state.json"

def escape_html(text):
    """Экранирует спецсимволы для Telegram HTML"""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

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

def clean_description(text):
    """Очищает ответ модели от мусора и форматирования"""
    if not text:
        return text
    
    # Убираем Markdown-форматирование
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Убираем префиксы типа "Краткое описание:", "Вот описание:" и т.п.
    text = re.sub(r'^(?:краткое\s+)?описание[:\.]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^вот\s+(?:краткое\s+)?описание[:\.]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^описание\s+сериала[:\.]?\s*', '', text, flags=re.IGNORECASE)
    
    # Убираем типовые преамбулы модели
    trash_prefixes = [
        r'^(?:конечно|разумеется|хорошо|безусловно|итак)[\s,!.]*',
        r'^у меня нет (?:прямого )?доступа к интернету[^.]*\.\s*',
        r'^я не могу (?:искать|найти)[^.]*интернет[^.]*\.\s*(?:но\s+)?',
        r'^я могу составить[^.]*на основе[^.]*\.\s*',
        r'^могу (?:предложить|составить)[^.]*\.\s*',
    ]
    for pattern in trash_prefixes:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Убираем ведущие "**", если остались
    text = text.lstrip('*').lstrip()
    
    return text

def get_gigachat_description(playlist_title):
    credentials = os.environ.get("GIGACHAT_CREDENTIALS")
    if not credentials:
        print("[gigachat] credentials not found")
        return None
    
    # Автоматически добавляем 'Basic ' если его нет
    if not credentials.startswith("Basic "):
        credentials = f"Basic {credentials}"
        print("[gigachat] added 'Basic ' prefix to credentials")
    
    try:
        # 1. Получаем access token
        rq_uid = str(uuid.uuid4())
        token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": rq_uid,
            "Authorization": credentials
        }
        token_data = {"scope": "GIGACHAT_API_PERS"}
        
        print(f"[gigachat] requesting token (RqUID: {rq_uid})...")
        token_resp = requests.post(
            token_url,
            headers=token_headers,
            data=token_data,
            verify=False,
            timeout=30
        )
        
        if token_resp.status_code != 200:
            print(f"[gigachat] token request failed: {token_resp.status_code}")
            print(f"[gigachat] response: {token_resp.text}")
            return None
        
        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        
        if not access_token:
            print("[gigachat] no access token in response")
            return None
        
        # 2. Генерируем описание через НОВЫЙ endpoint api.giga.chat
        chat_url = "https://api.giga.chat/v1/chat/completions"
        chat_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        # Промпт с требованиями к стилю
        prompt = (
            f"Составь краткое описание (2-3 предложения) документального сериала "
            f"'{playlist_title}' производства National Geographic. "
            f"Используй свои знания о сериале, его тематике и содержании.\n\n"
            f"ТРЕБОВАНИЯ К СТИЛЮ:\n"
            f"- Пиши живо, естественно, как будто рассказываешь другу о интересном фильме\n"
            f"- Используй разговорный, но грамотный язык\n"
            f"- Избегай канцеляризмов и шаблонных фраз вроде 'погружает зрителей', 'раскрывает перед нами'\n"
            f"- Описание должно начинаться каждый раз по-разному. Возможные варианты начала:\n"
            f"  * Сразу с сути: 'Этот сериал о...'\n"
            f"  * С вопроса: 'Вы когда-нибудь задумывались...?'\n"
            f"  * С факта: 'Мало кто знает, что...'\n"
            f"  * С эмоции: 'Невероятная история о...'\n"
            f"  * С места действия: 'В глубинах океана...'\n"
            f"- Не начинай каждое описание со слов 'Этот сериал' или 'Документальный фильм'\n"
            f"- Будь креативным, но не выдумывай фактов\n\n"
            f"ВАЖНО:\n"
            f"- Начинай сразу с описания, без преамбул типа 'Конечно!' или 'Вот описание:'\n"
            f"- Не используй markdown-форматирование (звёздочки, подчёркивания)\n"
            f"- Пиши простым текстом, 2-3 предложения максимум"
        )
        
        chat_payload = {
            "model": "GigaChat-3-Ultra",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 300
        }
        
        print(f"[gigachat] generating description with GigaChat-3-Ultra...")
        chat_resp = requests.post(
            chat_url,
            headers=chat_headers,
            json=chat_payload,
            verify=False,
            timeout=30
        )
        
        if chat_resp.status_code != 200:
            print(f"[gigachat] chat request failed: {chat_resp.status_code}")
            print(f"[gigachat] response: {chat_resp.text}")
            return None
        
        chat_json = chat_resp.json()
        choices = chat_json.get("choices", [])
        if choices:
            raw_description = choices[0].get("message", {}).get("content", "").strip()
            description = clean_description(raw_description)
            print(f"[gigachat] raw: {raw_description[:100]}...")
            print(f"[gigachat] cleaned: {description[:100]}...")
            if description:
                return description
        
        print("[gigachat] no usable content in response")
        return None
        
    except Exception as e:
        print(f"[gigachat] exception: {type(e).__name__}: {e}")
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

    albums_resp = api_call(s, "video.getAlbums", token,
                           owner_id=OWNER_ID, count="100")
    albums = albums_resp.get("items", []) if isinstance(albums_resp, dict) else []
    print(f"playlists: {len(albums)}")
    if not albums:
        print("no playlists, exit")
        return

    state = load_state()
    p_idx = state.get("playlist_index", 0) % len(albums)

    album = albums[p_idx]
    album_id = album["id"]
    album_title = album.get("title", "Без названия").strip()
    print(f"current: #{p_idx} '{album_title}'")

    desc = get_gigachat_description(album_title)
    if not desc:
        desc = "Документальный сериал National Geographic."
    desc = escape_html(desc)

    playlist_url = f"https://vkvideo.ru/playlist/{OWNER_ID}_{album_id}"
    safe_title = escape_html(album_title)
    post = (
        f"📺 <b>Сегодня в эфире</b>\n\n"
        f'🎬 <a href="{playlist_url}"><b>{safe_title}</b></a>\n\n'
        f"{desc}"
    )
    print("\n--- POST ---")
    print(post)
    print("------------\n")
    send_telegram(post)

    p_idx = (p_idx + 1) % len(albums)
    save_state({"playlist_index": p_idx})
    print(f"state saved: next playlist={p_idx}")

if __name__ == "__main__":
    main()
