import re
import asyncio

CHANNEL_URL = "https://vkvideo.ru/@natgeostream/playlists"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

async def run():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"], locale="ru-RU")
        page = await context.new_page()

        xhr = []
        page.on("response", lambda r: xhr.append(r.url)
                if r.request.resource_type in ("xhr", "fetch") else None)

        print("[browser] открываю страницу плейлистов...")
        await page.goto(CHANNEL_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Скроллим, пока количество ссылок растёт
        prev, stable = -1, 0
        for i in range(40):
            for sel in ("text=Показать ещё", "text=Показать еще"):
                try:
                    btn = page.locator(sel).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(1500)
                except Exception:
                    pass
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1200)
            cur = await page.eval_on_selector_all(
                'a[href*="/playlist/"]', "els => els.length")
            if cur == prev:
                stable += 1
                if stable >= 4:
                    break
            else:
                stable = 0
            prev = cur
        print(f"[browser] итераций скролла: {i+1}, ссылок: {prev}")

        data = await page.eval_on_selector_all(
            'a[href*="/playlist/"]',
            'els => els.map(e => ({href: e.getAttribute("href"), text: e.innerText.trim()}))')

        print("[browser] XHR/fetch запросы:")
        for u in sorted(set(xhr))[:60]:
            print("   ", u)

        # Склеиваем дубли: лучшее название = самое длинное, не "N видео"
        best, order = {}, []
        for item in data:
            href = (item["href"] or "").split("?")[0]
            if "/playlist/" not in href:
                continue
            if href not in best:
                best[href] = ""
                order.append(href)
            t = re.sub(r"\s+", " ", item["text"]).strip()
            if t and not re.fullmatch(r"\d+ видео", t) and len(t) > len(best[href]):
                best[href] = t

        print(f"\n=== ПЛЕЙЛИСТОВ: {len(order)} ===")
        for n, href in enumerate(order, 1):
            print(f"{n}. {best[href] or '—'} | {href}")

        # ПРОБА: открываем первый плейлист
        probe = "https://vkvideo.ru" + order[0]
        print(f"\n[probe] открываю {probe}")
        await page.goto(probe, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

        vids = await page.eval_on_selector_all(
            'a[href*="/video"]',
            'els => els.map(e => ({href: e.getAttribute("href"), text: e.innerText.trim()}))')
        seen, vlist = set(), []
        for v in vids:
            h = (v["href"] or "").split("?")[0]
            if h not in seen and "/video" in h:
                seen.add(h)
                vlist.append((h, re.sub(r"\s+", " ", v["text"])))
        print(f"[probe] уникальных видео-ссылок: {len(vlist)}")
        for h, t in vlist[:8]:
            print(f"   {h} | {t[:70]}")

        print("[probe] ищу описание плейлиста:")
        for sel in ('[class*="desc"]', '[class*="Desc"]', '[class*="about"]',
                    '[class*="info"]', '[class*="description"]'):
            try:
                els = await page.query_selector_all(sel)
            except Exception:
                continue
            for e in els[:3]:
                t = (await e.inner_text()).strip()
                if len(t) > 40:
                    print(f"   [{sel}] {t[:300]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
