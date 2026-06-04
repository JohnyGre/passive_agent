"""
PASSIVE AGENT — HLAVNÝ VSTUPNÝ BOD
Spusti: python main.py
"""

import logging
import sys
from pathlib import Path

# Windows konzola — UTF-8 pre emoji a slovenské znaky
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Logging nastavenie ───────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATE   = "%H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "output" / "logs" / "agent.log",
            encoding="utf-8"
        )
    ]
)

# ── Potlač spam logy z knižníc ───────────────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PASSIVE AGENT — Autonómny agent pre pasívny príjem")
    parser.add_argument("--now", action="store_true", help="Spustiť generovanie produktov okamžite")
    parser.add_argument("--publish-pending", action="store_true", help="Publikovať všetky doteraz nepublikované produkty na Gumroad")
    parser.add_argument("--report", action="store_true", help="Spustiť denný report okamžite")
    parser.add_argument("--scan-trends", action="store_true", help="Spustiť skenovanie trendov okamžite")
    args = parser.parse_args()

    # Vytvor output adresáre (config ich tvorí automaticky)
    from config import OUTPUT_DIR, PRODUCTS_DIR, LOGS_DIR  # noqa

    from agents.orchestrator import Orchestrator
    agent = Orchestrator()

    main_log = logging.getLogger("Main")

    if args.scan_trends:
        agent.job_trend_scan()
        return

    if args.now:
        main_log.info("Spúšťam okamžité generovanie produktov...")
        agent.job_generate_products()
        return

    if args.publish_pending:
        main_log.info("Spúšťam publikovanie všetkých doteraz nepublikovaných produktov...")
        results = agent.gumroad.publish_all_pending()
        main_log.info(f"Publikovanie dokončené. Publikovaných produktov: {len(results)}")
        return

    if args.report:
        main_log.info("Generujem denný report...")
        agent.job_daily_report()
        return

    agent.run()


if __name__ == "__main__":
    main()
