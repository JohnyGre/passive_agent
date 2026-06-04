"""
ORCHESTRÁTOR - PRO VERSION
Integruje ValidationAgenta s rozšírenou PRO validáciou.
Gumroad upload je dočasne vypnutý pre lokálne testovanie.
"""

import logging
import random
import time
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
    GUMROAD_ACCESS_TOKEN,
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

    def job_generate_products(self):
        log.info(f"Generujem {PRODUCTS_PER_DAY} nových PRO produktov (Gumroad upload vypnutý)...")

        if not self._current_trends:
            self._current_trends = self.trends.load_cache()

        if not self._current_trends:
            log.warning("Žiadne trendy")
            return

        sample = random.sample(self._current_trends, min(PRODUCTS_PER_DAY, len(self._current_trends)))
        product_types = ["mini_guide", "prompt_pack"] 

        for i, trend in enumerate(sample):
            topic = trend["keyword"]
            score = trend.get("score", 70)
            ptype = product_types[i % len(product_types)]
            suggested_price = self._calculate_price(score)

            log.info(f"🚀 [Produkt {i+1}/{len(sample)}] Téma: {topic}")

            try:
                # 1. Generovanie hĺbkového obsahu a kódu
                product = self.content.generate(topic, ptype)
                if not product: continue
                product["_meta"]["suggested_price"] = suggested_price

                # 2. PRO VALIDÁCIA KÓDU
                python_code = product.get("python_script") or product.get("python_helper")
                if python_code:
                    log.info("  Spúšťam PRO validáciu kódu...")
                    is_valid, msg = self.validator.validate_pro_features(python_code)
                    product["code_valid"] = is_valid
                    if is_valid:
                        log.info("  ✅ Kód prešiel PRO validáciou.")
                    else:
                        log.warning(f"  ⚠️ Kód neprešiel PRO validáciou: {msg}")

                # 3. Ukladanie súborov (Vytvorí v1_DIY a v2_PRO)
                paths = self.files.save(product)
                product_dir = paths["json"].parent
                self.reporter.record("product_created", {"title": product.get("title", topic), "type": ptype})

                # 4. Marketing & Cover
                m_data = self.marketing.generate_marketing(product)
                if m_data: self.marketing.save_marketing(m_data, product_dir)
                cover_path = self.cover.generate_cover(product, folder=product_dir)

                # 5. Gumroad (Upload je dočasne vypnutý)
                log.info("  Gumroad upload je dočasne vypnutý pre lokálne testovanie.")
                
                log.info(f"✅ Hotovo pre: {topic}")

            except Exception as e:
                log.error(f"❌ Chyba pri '{topic}': {e}")

    def job_trend_scan(self):
        log.info("Skenujem trendy...")
        try:
            self._current_trends = self.trends.scan()
            self.reporter.record("trend_scan")
        except Exception as e:
            log.error(f"Trend scan zlyhal: {e}")

    def job_daily_report(self):
        self.reporter.daily_report()

    def run(self):
        log.info("=" * 50)
        log.info("  PASSIVE AGENT PRO: UNIVERSAL AUTOMATION READY (LOCAL TEST MODE)")
        log.info("=" * 50)
        self.job_trend_scan()
        self._register_jobs()
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            self.scheduler.shutdown()

    def _register_jobs(self):
        self.scheduler.add_job(self.job_trend_scan, CronTrigger.from_crontab(SCHEDULE["trend_scan"]), id="trend_scan")
        self.scheduler.add_job(self.job_generate_products, CronTrigger.from_crontab(SCHEDULE["content_gen"]), id="content_gen")
        self.scheduler.add_job(self.job_daily_report, CronTrigger.from_crontab(SCHEDULE["daily_report"]), id="daily_report")
