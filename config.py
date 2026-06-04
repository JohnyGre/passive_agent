# ══════════════════════════════════════════════
#  PASSIVE AGENT — KONFIGURÁCIA (PRO MODEL UPDATE)
# ══════════════════════════════════════════════

import os
from pathlib import Path

# ── Načítanie .env ────────────────────────────
BASE_DIR     = Path(__file__).parent
env_path     = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# ── Adresáre ────────────────────────────────
OUTPUT_DIR   = BASE_DIR / "output"
PRODUCTS_DIR = OUTPUT_DIR / "products"
LOGS_DIR     = OUTPUT_DIR / "logs"

for d in [OUTPUT_DIR, PRODUCTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Ollama (VÝBER MODELU) ───────────────────
OLLAMA_URL   = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# ODPORÚČANÉ MODELY:
# 1. "qwen2.5-coder:32b" - Najlepší pre Python skripty + JSON (Môj výber)
# 2. "deepseek-v3"       - Najvyššia celková inteligencia
# 3. "llama3.3"          - Najlepší pre kreatívny text (Marketing)

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:32b")

# ── Google Trends ───────────────────────────
TRENDS_GEO       = "SK"               
TRENDS_GEO_WIDE  = ""                 
TRENDS_TIMEFRAME = "now 7-d"

# Témy pre generovanie produktov
PRODUCT_TOPICS = [
    "AI prompts",
    "ChatGPT productivity",
    "Python automation",
    "passive income online",
    "freelance tools",
    "Midjourney prompts",
    "digital marketing",
    "side hustle ideas",
]

# ── Produkty ────────────────────────────────
PRODUCTS_PER_DAY  = 10                

# ── Rozvrh (24/7) ───────────────────────────
SCHEDULE = {
    "trend_scan":    "0 */4 * * *",  
    "content_gen":   "0 3   * * *",  
    "daily_report":  "0 17  * * *",  
}

# ── Gumroad ─────────────────────────────────
GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
GUMROAD_EMAIL        = os.environ.get("GUMROAD_EMAIL", "")
GUMROAD_PASSWORD     = os.environ.get("GUMROAD_PASSWORD", "")
PRODUCT_PRICE_USD    = 7.99 

# ── Telegram ────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
