"""Inspekcia Gumroad login formulara v cistom headless kontexte."""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()
        await page.goto("https://gumroad.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        data = await page.evaluate("""() => {
            const inputs = [...document.querySelectorAll('input')].map(i => ({name:i.name, id:i.id, type:i.type, ariaLabel:i.getAttribute('aria-label'), autocomplete:i.getAttribute('autocomplete')}));
            const buttons = [...document.querySelectorAll('button')].map(b => ({type:b.type, text:b.innerText.trim()}));
            return {url: location.href, title: document.title, inputs, buttons};
        }""")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        await browser.close()

asyncio.run(main())
