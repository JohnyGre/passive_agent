"""
Nahrá existujúce produkty z outputu na Gumroad s covermi
"""
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
log = logging.getLogger("UploadExisting")

from config import PRODUCTS_DIR, GUMROAD_ACCESS_TOKEN
from agents.gumroad_agent import GumroadAgent
from agents.cover_uploader import CoverUploader
from config import GUMROAD_EMAIL, GUMROAD_PASSWORD

def upload_all():
    if not GUMROAD_ACCESS_TOKEN:
        log.error("❌ GUMROAD_ACCESS_TOKEN nie je nastavený v .env")
        return
    
    gumroad = GumroadAgent()
    uploader = CoverUploader(GUMROAD_EMAIL, GUMROAD_PASSWORD) if (GUMROAD_EMAIL and GUMROAD_PASSWORD) else None
    
    # Nájdi všetky produktové zložky
    product_dirs = sorted([d for d in PRODUCTS_DIR.iterdir() if d.is_dir()], reverse=True)
    
    log.info(f"Nájdených {len(product_dirs)} produktov.")
    
    for i, product_dir in enumerate(product_dirs, 1):
        log.info(f"\n🚀 [{i}/{len(product_dirs)}] Nahrávam: {product_dir.name}")
        
        try:
            # 1. Nahraj na Gumroad
            result = gumroad.publish_product_dir(product_dir, price=7.99)
            
            if result:
                log.info(f"✅ Produkt live: {result['url']}")
                
                # 2. Nahraj cover cez Playwright
                cover_path = product_dir / "cover.jpg"
                if cover_path.exists() and uploader:
                    log.info(f"  Nahrávam cover...")
                    uploader.upload_sync(result["product_id"], cover_path)
                elif cover_path.exists():
                    log.warning(f"  Cover existuje ale Playwright nie je nastavený")
            else:
                log.warning(f"⚠️  Gumroad upload zlyhal")
        
        except Exception as e:
            log.error(f"❌ Chyba: {e}")

if __name__ == "__main__":
    upload_all()
