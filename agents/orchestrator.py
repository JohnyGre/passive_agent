"""
ORCHESTRÁTOR - PRO VERSION 2.0
Zabezpečuje robustnú linku, vylepšenú validáciu a agresívnu správu VRAM.
"""

import logging
import random
import time
import gc  # Garbage Collector pre uvoľňovanie RAM
import torch # Pre manuálne uvoľňovanie VRAM
import re # Pre extrakciu Python kódu
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.trend_agent      import TrendAgent
from agents.content_agent    import ContentAgent
from agents.file_agent       import FileAgent
from agents.reporter         import Reporter
from agents.gumroad_agent    import GumroadAgent
from agents.cover_agent      import CoverAgent
from agents.cover_uploader   import CoverUploader
from agents.marketing_agent  import MarketingAgent
from agents.validation_agent import ValidationAgent
from config import (
    SCHEDULE,
    PRODUCTS_PER_DAY,
    GUMROAD_ACCESS_TOKEN, # Importujeme GUMROAD_ACCESS_TOKEN
    GUMROAD_EMAIL,
    GUMROAD_PASSWORD,
)

log = logging.getLogger("Orchestrator")

class Orchestrator:

    def __init__(self):
        self.scheduler = BlockingScheduler(timezone="Europe/Bratislava")
        self.trends    = TrendAgent()
        self.content   = ContentAgent()
        self.files     = FileAgent()
        self.reporter  = Reporter()
        self.gumroad   = GumroadAgent()
        self.cover     = CoverAgent()
        self.marketing = MarketingAgent()
        self.validator = ValidationAgent()
        self.uploader  = CoverUploader(GUMROAD_EMAIL, GUMROAD_PASSWORD)

        self._current_trends = []

    def _calculate_price(self, trend_score: int) -> float:
        if trend_score >= 85: return 12.99
        if trend_score >= 70: return 7.99
        return 4.99

    def _cleanup_resources(self):
        """Agresívne uvoľňovanie pamäte medzi agentmi (Kľúčové pre 4GB VRAM)."""
        log.info("🧹 Vyčisťujem zdroje (RAM/VRAM)...")
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    def _extract_python_code(self, text: str) -> str:
        """Extrahuje Python kód z markdown bloku (```python, ```py, alebo len ```)."""
        # Hľadá ```python, ```py, alebo len ``` a extrahuje obsah
        match = re.search(r'```(?:python|py)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip() # Ak nenájdeme markdown, vrátime celý text

    def job_generate_products(self):
        log.info(f"🚀 Spúšťam výrobnú linku: {PRODUCTS_PER_DAY} nových produktov...")

        if not self._current_trends:
            self._current_trends = self.trends.load_cache()

        if not self._current_trends:
            log.warning("❌ Žiadne trendy k spracovaniu.")
            return

        # Získaj všetky už vygenerované safe názvy tém z priečinka
        from config import PRODUCTS_DIR
        existing_safes = set()
        if PRODUCTS_DIR.exists():
            for d in PRODUCTS_DIR.iterdir():
                if d.is_dir():
                    # Zložky sú pomenované YYYYMMDD_HHMMSS_safe_name
                    parts = d.name.split("_", 2)
                    if len(parts) >= 3:
                        existing_safes.add(parts[2].lower())
                    else:
                        existing_safes.add(d.name.lower())

        # Vyfiltruj trendy, ktoré už boli vygenerované
        filtered_trends = []
        for trend in self._current_trends:
            topic = trend["keyword"]
            safe_topic = self.files._safe_filename(topic).lower()
            if safe_topic in existing_safes:
                log.info(f"⏭️ Preskakujem už vygenerovanú tému (duplicita): {topic}")
                continue
            filtered_trends.append(trend)

        if not filtered_trends:
            log.warning("❌ Všetky dostupné trendy už boli vygenerované (žiadne nové témy na spracovanie).")
            return

        sample = random.sample(filtered_trends, min(PRODUCTS_PER_DAY, len(filtered_trends)))
        product_types = ["mini_guide", "prompt_pack"]

        for i, trend in enumerate(sample):
            topic = trend["keyword"]
            score = trend.get("score", 70)
            ptype = product_types[i % len(product_types)]
            suggested_price = self._calculate_price(score)

            log.info(f"📦 [Produkt {i+1}/{len(sample)}] Téma: {topic} | Typ: {ptype}")

            try:
                # 1. GENERÁCIA OBSAHU
                product = self.content.generate(topic, ptype)
                if not product:
                    log.error(f"❌ Generovanie obsahu zlyhalo pre {topic}")
                    continue

                product["_meta"]["suggested_price"] = suggested_price

                # Okamžite uvoľniť pamäť po ContentAgente, aby bolo miesto pre CoverAgent
                self._cleanup_resources()

                # 2. PRO VALIDÁCIA + RETRY LOOP (max 2 pokusy o opravu)
                raw_python_code = product.get("pro_kit", {}).get("scripts", [{}])[0].get("content")
                if not raw_python_code:
                    raw_python_code = product.get("python_script") or product.get("python_helper")

                if raw_python_code:
                    python_code = self._extract_python_code(raw_python_code)
                    log.info("  🔍 Spúšťam komplexnú PRO validáciu kódu...")
                    is_valid, issues = self.validator.full_check(python_code)

                    # RETRY: Ak kód neprešiel, pokús sa ho opraviť cez LLM
                    if not is_valid:
                        log.warning(f"  ⚠️ Kód má nedostatky, pokúšam sa o opravu...")
                        for retry in range(2):
                            fixed_code = self._try_fix_code(python_code, issues, topic)
                            if fixed_code:
                                python_code = fixed_code
                                is_valid, issues = self.validator.full_check(python_code)
                                if is_valid:
                                    log.info(f"  ✅ Kód opravený na pokus {retry+1}!")
                                    # Update product s opraveným kódom
                                    product["pro_kit"]["scripts"][0]["content"] = python_code
                                    break
                            self._cleanup_resources()

                    product["code_quality"] = {
                        "is_valid": is_valid,
                        "issues": issues
                    }
                    if is_valid:
                        log.info("  ✅ Kód prešiel všetkými PRO testami.")
                    else:
                        log.warning(f"  ⚠️ Kód má nedostatky: {', '.join(issues)}")

                # 3. UKLADANIE (Vytvorí v1_DIY a v2_PRO)
                paths = self.files.save(product)
                product_dir = paths["json"].parent
                product_title = product.get("metadata", {}).get("title") or product.get("title", topic)
                self.reporter.record("product_created", {"title": product_title, "type": ptype})

                # 4. MARKETING (Cover generovanie je dočasne vypnuté)
                log.info("  🎨 Generujem marketingové materiály...")
                m_data = self.marketing.generate_marketing(product)
                if m_data:
                    self.marketing.save_marketing(m_data, product_dir)

                # Cover generovanie (lokálne SD - VRAM je voľná, obsah beží cez cloud)
                log.info("  🖼️ Generujem produktový cover (Stable Diffusion)...")
                cover_path = None # Inicializujeme cover_path
                try:
                    cover_path = self.cover.generate_cover(product, folder=product_dir)
                    if cover_path:
                        log.info(f"  ✅ Cover hotový: {cover_path.name}")
                    else:
                        log.warning("  ⚠️ Cover sa nevygeneroval (pokračujem bez neho).")
                except Exception as cover_err:
                    log.error(f"  ❌ Cover generovanie zlyhalo (produkt zostáva platný): {cover_err}")

                self._cleanup_resources()

                # 5. GUMROAD UPLOAD
                if GUMROAD_ACCESS_TOKEN: # Ak je token definovaný, pokúsime sa uploadovať
                    log.info("  ⬆️ Nahrávam produkt na Gumroad...")
                    try:
                        gumroad_result = self.gumroad.publish_product_dir(product_dir, suggested_price, cover_path)
                        if gumroad_result:
                            log.info("  ✅ Produkt úspešne nahraný na Gumroad.")
                        else:
                            log.warning("  ⚠️ Produkt sa nenahral na Gumroad.")
                    except Exception as gumroad_err:
                        log.error(f"  ❌ Gumroad upload zlyhal pre '{product_title}': {gumroad_err}", exc_info=True) # Pridané exc_info
                else:
                    log.info("  🛒 Gumroad upload je vypnutý (GUMROAD_ACCESS_TOKEN nie je nastavený).")

                log.info(f"🏁 Hotovo pre: {topic}")

            except Exception as e:
                log.error(f"💥 Kritická chyba pri '{topic}': {e}", exc_info=True)
                self._cleanup_resources() # Pri chybe aj tak vyčistiť, aby ďalší produkt nepadol

        log.info("✅ Celý výrobný cyklus dokončený.")

    def _try_fix_code(self, code: str, issues: list, topic: str) -> str | None:
        """Pokúsi sa opraviť kód cez LLM na základe nájdených problémov."""
        import httpx
        from config import OLLAMA_URL, OLLAMA_MODEL

        fix_prompt = f"""CRITICAL: Fix this Python code. The following issues were found:
{chr(10).join(f'- {i}' for i in issues)}

⚠️ THE PREVIOUS VERSION WAS REJECTED. Common reasons for rejection:
- time.sleep() used to simulate API calls instead of making real HTTP requests
- Hardcoded/mock data returned instead of actually fetching from the web
- random.choice() used to fake scraped results
- Comments like "# simulated", "# mock", "# placeholder"
- Functions returning static dicts/lists without any real HTTP call

ABSOLUTELY FORBIDDEN PATTERNS (your code will be REJECTED AGAIN if ANY are found):
- time.sleep() to simulate/fake API calls or processing delays
- Hardcoded/mock data pretending to be API responses
- Comments containing: "simulated", "mock", "placeholder", "example only", "demo", "dummy", "fake"
- Functions that return static strings/dicts/lists instead of making real HTTP requests
- Using random.choice() or random.sample() to fake scraped/generated results
- Using 'example.com' or any placeholder URL

MANDATORY REQUIREMENTS:
- MUST use requests.get()/requests.post() or httpx.get()/httpx.post() with REAL URLs
- MUST parse HTML with BeautifulSoup if scraping: from bs4 import BeautifulSoup
- MUST handle HTTP errors: check response.status_code, try/except for ConnectionError, Timeout
- MUST include User-Agent header in HTTP requests
- MUST have configurable target URLs via argparse or config variables
- If the script needs AI/LLM: MUST connect to real API (Ollama http://localhost:11434 or OpenAI-compatible)
- The user must only need to set their API URL/key — no simulated AI responses

RULES:
1. Use ONLY standard Python libraries or: httpx, apscheduler, pytrends, requests, python-docx, beautifulsoup4.
2. DO NOT use flask, django, fastapi, notion_client, googlesearch, or any unlisted library.
3. Every function MUST have a docstring and type hints.
4. Code MUST include try/except error handling.
5. Output ONLY the fixed Python code, no explanations.

Original code:
```python
{code}
```"""

        try:
            client = httpx.Client(timeout=120.0)
            resp = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": fix_prompt,
                    "stream": False,
                    "keep_alive": 0,
                    "options": {"temperature": 0.1, "num_predict": 4096}
                }
            )
            client.close()
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            fixed = self._extract_python_code(raw)
            if fixed and len(fixed) > 20:
                return fixed
        except Exception as e:
            log.error(f"Code fix attempt failed: {e}")
        return None

    def job_trend_scan(self):
        log.info("🔍 Skenujem trendy...")
        try:
            self._current_trends = self.trends.scan()
            self.reporter.record("trend_scan")
        except Exception as e:
            log.error(f"Trend scan zlyhal: {e}")

    def job_daily_report(self):
        self.reporter.daily_report()

    def run(self):
        log.info("=" * 50)
        log.info("  PASSIVE AGENT PRO: UNIVERSAL AUTOMATION READY")
        log.info("=" * 50)
        self.job_trend_scan()
        self._register_jobs()
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            log.info("🛑 Zastavenie orchestrátora...")
            self.scheduler.shutdown()

    def _register_jobs(self):
        self.scheduler.add_job(self.job_trend_scan, CronTrigger.from_crontab(SCHEDULE["trend_scan"]), id="trend_scan")
        self.scheduler.add_job(self.job_generate_products, CronTrigger.from_crontab(SCHEDULE["content_gen"]), id="content_gen")
        self.scheduler.add_job(self.job_daily_report, CronTrigger.from_crontab(SCHEDULE["daily_report"]), id="daily_report")