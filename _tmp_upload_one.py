"""Jednorazový upload JEDNÉHO produktu na Gumroad vrátane coveru."""
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("UploadOne")

from config import PRODUCTS_DIR, GUMROAD_EMAIL, GUMROAD_PASSWORD
from agents.gumroad_agent import GumroadAgent
from agents.cover_uploader import CoverUploader

# Vyber NAJNOVŠÍ produkt
product_dir = sorted(
    [d for d in PRODUCTS_DIR.iterdir() if d.is_dir()],
    key=lambda p: p.stat().st_mtime, reverse=True,
)[0]
log.info(f"🎯 Produkt: {product_dir.name}")

gumroad = GumroadAgent()

# Ochrana proti duplicite
if product_dir.name in gumroad._published:
    log.warning(f"⏭️ Už publikovaný: {gumroad._published[product_dir.name]}")
    raise SystemExit(0)

result = gumroad.publish_product_dir(product_dir, price=7.99)
gumroad.close()

if not result:
    log.error("❌ Gumroad upload zlyhal — pozri log vyššie.")
    raise SystemExit(1)

log.info(f"✅ Produkt LIVE: {result['url']}  (id={result['product_id']})")

# Cover upload cez Playwright
cover_path = product_dir / "cover.jpg"
if cover_path.exists() and GUMROAD_EMAIL and GUMROAD_PASSWORD:
    log.info("🖼️ Nahrávam cover cez Playwright...")
    uploader = CoverUploader(GUMROAD_EMAIL, GUMROAD_PASSWORD)
    ok = uploader.upload_sync(result["product_id"], cover_path)
    log.info(f"Cover upload: {'✅ OK' if ok else '⚠️ zlyhal (produkt je aj tak live, cover sa dá doplniť)'}")
else:
    log.warning("⚠️ Cover alebo prihlasovacie údaje chýbajú — cover preskočený.")

log.info(f"🏁 HOTOVO. URL: {result['url']}")
