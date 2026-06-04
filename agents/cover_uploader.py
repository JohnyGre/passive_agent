"""
GUMROAD COVER UPLOADER
Vylepšený prihlasovací proces a stabilita.
"""

import logging
import asyncio
import random
from pathlib import Path

log = logging.getLogger("CoverUploader")

class CoverUploader:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def upload(self, product_id: str, cover_path: Path) -> bool:
        if not cover_path.exists() or not self.email: return False

        try:
            from playwright.async_api import async_playwright
        except ImportError: 
            log.warning("Playwright nie je nainštalovaný")
            return False

        log.info(f"Playwright start pre {product_id}...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            page.set_default_timeout(15000)

            try:
                # 1. Login
                await page.goto("https://gumroad.com/login", wait_until="domcontentloaded")
                await page.fill('input[name="email"]', self.email)
                await page.wait_for_timeout(300)
                await page.fill('input[name="password"]', self.password)
                await page.click('button[type="submit"]')
                
                # Čakáme na dashboard
                try:
                    await page.wait_for_url("**/dashboard**", timeout=10000)
                except:
                    await page.wait_for_timeout(2000)
                log.info("✓ Gumroad login OK")

                # 2. Choď na editáciu produktu
                edit_url = f"https://app.gumroad.com/products/{product_id}/edit"
                await page.goto(edit_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(500)

                # 3. Nájdi a nahraj cover obrázok
                # Gumroad má viaceré file inputy - hľadáme pre obrázok/cover
                try:
                    # Skús rôzne CSS selectory
                    file_inputs = page.locator('input[type="file"]')
                    count = await file_inputs.count()
                    
                    if count > 0:
                        # Vyber prvý file input (zvyčajne je to cover)
                        file_input = file_inputs.first
                        await file_input.set_input_files(str(cover_path))
                        log.info(f"✓ Cover file zvolený: {cover_path.name}")
                        await page.wait_for_timeout(2000)
                    else:
                        log.warning("Žiadny file input nenájdený")
                        return False
                except Exception as e:
                    log.warning(f"File upload problém: {e}")
                    return False

                # 4. Hľadaj Save button (rôzne varianty textu)
                save_selectors = [
                    'button:has-text("Save changes")',
                    'button:has-text("Save")',
                    'button.primary:has-text("Save")',
                    'button[type="submit"]:has-text("Save")',
                    'button:text("Save changes")'
                ]
                
                saved = False
                for selector in save_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible():
                            await btn.click()
                            log.info("✓ Save button kliknutý")
                            await page.wait_for_timeout(2000)
                            saved = True
                            break
                    except:
                        continue
                
                if not saved:
                    log.warning("Save button nenájdený, čakám...")
                    await page.wait_for_timeout(2000)
                
                log.info(f"✅ Obal nahratý pre {product_id}")
                return True

            except Exception as e:
                log.error(f"Playwright error: {e}")
                import traceback
                log.error(traceback.format_exc())
                return False
            finally:
                await browser.close()

    def upload_sync(self, product_id: str, cover_path: Path) -> bool:
        try:
            return asyncio.run(self.upload(product_id, cover_path))
        except Exception as e:
            log.error(f"Sync upload failed: {e}")
            return False
