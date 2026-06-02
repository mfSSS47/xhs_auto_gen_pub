"""Search Xiaohongshu for posts, read notes, by keyword.
Standalone — no web dependencies for use via CLI or subprocess.
"""
import asyncio
import re
import sys
import urllib.parse

from playwright.async_api import async_playwright
from models.database import SessionLocal
from models.user import Account
from core.security import decrypt_credential

SKIP_LINES = [
    "创作中心", "业务合作", "发现", "RED", "直播", "发布", "消息", "通知", "我",
    "首页", "关于我们", "沪ICP", "营业执照", "行吟信息", "举报", "算法",
    "个性化", "收起侧边栏", "筛选", "大家都在搜", "猜你想搜",
    "LIVE", "笔记管理", "数据看板", "笔记灵感", "创作学院",
]


def _get_cookies():
    db = SessionLocal()
    acct = db.query(Account).filter(Account.platform == "xhs", Account.status == "active").first()
    if not acct:
        db.close()
        raise RuntimeError("No active XHS account")
    cred = decrypt_credential(acct.credential)
    cookies = {}
    for p in cred.split(";"):
        p = p.strip()
        if "=" in p:
            k, v = p.split("=", 1)
            cookies[k.strip()] = v.strip()
    db.close()
    return cookies


async def search(keyword: str, count: int = 10) -> list[dict]:
    cookies = _get_cookies()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        await ctx.add_cookies([
            {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
            for k, v in cookies.items()
        ])
        page = await ctx.new_page()

        kw = urllib.parse.quote(keyword)
        await page.goto(
            f"https://www.xiaohongshu.com/search_result?keyword={kw}&source=web_search_result_notes",
            wait_until="domcontentloaded", timeout=30000,
        )
        await page.wait_for_timeout(4000)

        posts = await page.evaluate(f"""() => {{
            const items = [];
            document.querySelectorAll('section.note-item').forEach(el => {{
                const title = (el.querySelector('.title span')?.textContent || '').trim();
                const author = (el.querySelector('.author .name')?.textContent || '').trim();
                const likes = (el.querySelector('.like-wrapper .count')?.textContent || '').trim();
                const link = (el.querySelector('a[href*="/explore/"]')?.href || '');
                if (title && title.length > 1) items.push({{title, author, likes, link}});
            }});
            return items.slice(0, {count});
        }}""")

        return posts


async def read_note_by_index(search_keyword: str, index: int = 0) -> dict:
    cookies = _get_cookies()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        await ctx.add_cookies([
            {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
            for k, v in cookies.items()
        ])
        page = await ctx.new_page()

        kw = urllib.parse.quote(search_keyword)
        await page.goto(
            f"https://www.xiaohongshu.com/search_result?keyword={kw}&source=web_search_result_notes",
            wait_until="domcontentloaded", timeout=30000,
        )
        await page.wait_for_timeout(4000)

        cards = page.locator("section.note-item a[href*='/search_result/']")
        count = await cards.count()
        if count > index:
            await cards.nth(index).click()
            await page.wait_for_timeout(4000)

        full_text = await page.evaluate("() => (document.body.innerText || '')")

        lines = [l.strip() for l in full_text.split("\n") if l.strip()
                 and not any(k in l for k in SKIP_LINES)]

        title = lines[0] if lines else ""
        body_lines = []
        in_body = False
        for l in lines[1:]:
            if not in_body:
                if len(l) > 15 and "关注" in l:
                    in_body = True
                continue
            if "共 " in l and "条评论" in l:
                break
            if l in ("- THE END -", "说点什么..."):
                break
            body_lines.append(l)
        body = "\n".join(body_lines)

        if not body.strip():
            body = await page.evaluate(
                "() => (document.querySelector('#detail-desc')?.textContent || '').trim()"
            )

        return {"title": title, "body": body, "url": page.url}


async def read_note_by_url(explore_url: str) -> dict:
    note_id_match = re.search(r'([a-f0-9]{24})', explore_url)
    note_id = note_id_match.group(1) if note_id_match else ""
    if not note_id:
        return {"error": "Could not extract note ID from URL"}
    return await read_note_by_index(note_id, 0)


# ── CLI ──────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法: python search_xhs.py <关键词> [数量]")
        print("       python search_xhs.py --read <关键词> [索引]")
        print("       python search_xhs.py --read-url <帖子URL>")
        print("       python search_xhs.py --json <关键词>")
        return

    if sys.argv[1] == "--json":
        import json
        keyword = sys.argv[2]
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        posts = asyncio.run(search(keyword, count))
        print(json.dumps(posts, ensure_ascii=False))
        return

    if sys.argv[1] == "--read" and len(sys.argv) > 2:
        keyword = sys.argv[2]
        index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        note = asyncio.run(read_note_by_index(keyword, index))
        import json
        print(json.dumps(note, ensure_ascii=False))
        return

    if sys.argv[1] == "--read-url" and len(sys.argv) > 2:
        note = asyncio.run(read_note_by_url(sys.argv[2]))
        print(f"标题: {note.get('title', 'N/A')}")
        print(f"正文:")
        print(note.get('body', ''))
        return

    keyword = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    posts = asyncio.run(search(keyword, count))
    for i, p in enumerate(posts):
        print(f"{i+1}. [{p['author']}] {p['title']}")
        print(f"   ❤{p['likes']}  {p['link']}")


if __name__ == "__main__":
    main()
