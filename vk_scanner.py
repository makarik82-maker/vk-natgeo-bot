import re
import asyncio
import requests

CHANNEL_URL = "https://vkvideo.ru/@natgeostream/playlists"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

def light_parse():
    r = requests.get(CHANNEL_URL, headers=HEADERS, timeout=30)
    print(f"[light] status={r.status_code} size={len(r.text)}")
    ids = []
    for m in re.finditer(r"/playlist/(-?\d+_\d+)", r.text):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids

async def browser_parse():
    from playwright.async_api import async_playwright
    results = []
    api_hits = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="ru-RU",
        )
        page = await context.new_page()

        def on_response(res):
            if "playlist" in res.url and "natgeostream" not in res.url:
                api_hits.add(res.url)
        page.on("response", on_response)

        print("[browser] открываю страницу...")
        await page.goto(CHANNEL_URL, wait_until="domcontentloaded", timeout=60000)
        for _ in range(5):  # прокрутка, чтобы подгрузились все карточки
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(700)
        await page.wait_for_timeout(2000)

        links = await page.query_selector_all('a[href*="/playlist/"]')
        print(f"[browser] ссылок на плейлисты в DOM: {len(links)}")
        seen = set()
        for a in links:
            href = await a.get_attribute("href") or ""
            if "/playlist/" not in href or href in seen:
                continue
            seen.add(href)
            text = (await a.inner_text()).strip().replace("\n", " ")
            results.append({"href": href, "title": text})
        await browser.close()

    print("[browser] перехваченные XHR со словом playlist:")
    for u in sorted(api_hits):
        print("   ", u)
    return results

def get_meta(html, prop):
    m = re.search(r'<meta[^>]+property="%s"[^>]+content="([^"]*)"' % prop, html)
    if not m:
        m = re.search(r'<meta[^>]+content="([^"]*)"[^>]+property="%s"' % prop, html)
    return m.group(1) if m else ""

def main():
    ids = light_parse()
    if ids:
        print("[light] нашлись плейлисты в HTML:", ids)
        items = [{"href": f"/playlist/{i}", "title": ""} for i in ids]
    else:
        print("[light] в HTML пусто — запускаю браузер")
        items = asyncio.run(browser_parse())

    print(f"\n=== НАЙДЕНО ПЛЕЙЛИСТОВ: {len(items)} ===")
    for n, it in enumerate(items, 1):
        url = it["href"]
        if url.startswith("/"):
            url = "https://vkvideo.ru" + url
        title = it.get("title", "")
        desc = ""
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            title = title or get_meta(r.text, "og:title")
            desc = get_meta(r.text, "og:description") or get_meta(r.text, "description")
        except Exception as e:
            print("meta error:", e)
        print(f"{n}. {title}")
        print(f"   URL: {url}")
        print(f"   DESC: {desc[:200]}")

if __name__ == "__main__":
    main()
