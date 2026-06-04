"""
REPORTER AGENT
Logovanie, denný súhrn, Telegram notifikácie (voliteľné).
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path

from config import LOGS_DIR, PRODUCTS_DIR, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger("Reporter")


class Reporter:

    def __init__(self):
        self.stats_file = LOGS_DIR / "stats.json"
        self.stats      = self._load_stats()

    # ── Zaznamenaj udalosť ───────────────────────────────────
    def record(self, event: str, data: dict = None):
        today = str(date.today())
        if today not in self.stats:
            self.stats[today] = {
                "products_generated": 0,
                "trends_scanned":     0,
                "errors":             0,
                "products":           []
            }

        day = self.stats[today]

        if event == "product_created":
            day["products_generated"] += 1
            if data:
                day["products"].append({
                    "title": data.get("title", "?"),
                    "type":  data.get("type",  "?"),
                    "time":  datetime.now().strftime("%H:%M")
                })
        elif event == "trend_scan":
            day["trends_scanned"] += 1
        elif event == "error":
            day["errors"] += 1
            log.error(f"Chyba zaznamennaná: {data}")

        self._save_stats()

    # ── Denný report ─────────────────────────────────────────
    def daily_report(self) -> str:
        today     = str(date.today())
        day_stats = self.stats.get(today, {})

        total_products = sum(
            v.get("products_generated", 0)
            for v in self.stats.values()
            if isinstance(v, dict)
        )

        # Spočítaj súbory
        product_files = list(PRODUCTS_DIR.rglob("*.txt"))

        report = f"""
╔══════════════════════════════════════╗
║   PASSIVE AGENT — DENNÝ REPORT      ║
╚══════════════════════════════════════╝

📅 Dátum:      {today}
⏰ Čas:        {datetime.now().strftime("%H:%M:%S")}

─── DNES ───────────────────────────────
✅ Produkty vytvorené:  {day_stats.get('products_generated', 0)}
📊 Trend skeny:         {day_stats.get('trends_scanned', 0)}
❌ Chyby:               {day_stats.get('errors', 0)}

─── CELKOVO ────────────────────────────
📦 Všetky produkty:     {total_products}
💾 Súbory na disku:     {len(product_files)}

─── POSLEDNÉ PRODUKTY ──────────────────"""

        products_today = day_stats.get("products", [])
        if products_today:
            for p in products_today[-5:]:
                report += f"\n  [{p['time']}] {p['title']}"
        else:
            report += "\n  (žiadne dnes)"

        report += f"\n\n{'─'*40}\n"
        report += "📂 Produkty uložené v:\n"
        report += f"   {PRODUCTS_DIR}\n"

        log.info(report)

        # Telegram notifikácia
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            self._send_telegram(report)

        return report

    # ── Telegram ─────────────────────────────────────────────
    def _send_telegram(self, message: str):
        try:
            import httpx
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            httpx.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text":    message[:4096],
                "parse_mode": "HTML"
            }, timeout=10)
            log.info("Telegram notifikácia odoslaná")
        except Exception as e:
            log.warning(f"Telegram zlyhalo: {e}")

    # ── Persistencia ─────────────────────────────────────────
    def _load_stats(self) -> dict:
        if self.stats_file.exists():
            try:
                return json.loads(self.stats_file.read_text())
            except Exception:
                pass
        return {}

    def _save_stats(self):
        self.stats_file.write_text(
            json.dumps(self.stats, ensure_ascii=False, indent=2)
        )
