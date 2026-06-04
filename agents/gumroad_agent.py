"""
GUMROAD PUBLISHER AGENT
Zjednodušený a opravený upload súborov.
"""

import json
import logging
import httpx
from pathlib import Path
from datetime import datetime

from config import GUMROAD_ACCESS_TOKEN

log = logging.getLogger("GumroadAgent")

GUMROAD_API = "https://api.gumroad.com/v2"

class GumroadAgent:
    def __init__(self):
        self.token = GUMROAD_ACCESS_TOKEN
        self.client = httpx.Client(timeout=60.0)
        from config import PRODUCTS_DIR
        self.published_log = PRODUCTS_DIR.parent / "logs" / "published.json"
        self._published = self._load_published()

    def _load_published(self) -> dict:
        if self.published_log.exists():
            try: return json.loads(self.published_log.read_text())
            except Exception: pass
        return {}

    def _save_published(self):
        self.published_log.parent.mkdir(parents=True, exist_ok=True)
        self.published_log.write_text(json.dumps(self._published, ensure_ascii=False, indent=2))

    def publish_product_dir(self, product_dir: Path, price: float = 7.99) -> dict | None:
        # 1. Nájdi hlavný súbor (PDF alebo TXT)
        pdf_file = list(product_dir.glob("*.pdf"))
        txt_file = list(product_dir.glob("*.txt"))
        
        # Ignoruj marketing_x.txt
        txt_file = [f for f in txt_file if "marketing" not in f.name]
        
        main_file = pdf_file[0] if pdf_file else (txt_file[0] if txt_file else None)
        
        if not main_file:
            log.warning(f"Žiadny súbor v {product_dir.name}")
            return None

        log.info(f"Nahrávam {main_file.name} na Gumroad...")

        try:
            with open(main_file, "rb") as f:
                # Správny multipart/form-data formát
                files = {"product[file]": (main_file.name, f, "application/octet-stream")}
                data = {
                    "access_token": self.token,
                    "name": product_dir.name.split("_", 2)[-1].replace("_", " ").title(),
                    "price": int(price * 100),
                    "description": f"Premium digital product: {main_file.name}",
                    "published": "true"
                }
                
                resp = self.client.post(
                    f"{GUMROAD_API}/products",
                    data=data,
                    files=files
                )
            
            resp_data = resp.json()
            if resp_data.get("success"):
                p_id = resp_data["product"]["id"]
                url = resp_data["product"]["short_url"]
                log.info(f"✅ Produkt live: {url}")
                
                result = {"product_id": p_id, "url": url}
                self._published[product_dir.name] = result
                self._save_published()
                return result
            else:
                err_msg = resp_data.get('message', 'Unknown error')
                log.error(f"Gumroad error: {err_msg}")
                if resp_data.get('errors'):
                    log.error(f"Details: {resp_data['errors']}")
        except Exception as e:
            log.error(f"Chyba pri uploade: {e}")
        
        return None

    def publish_all_pending(self) -> list:
        """Publikuj všetky produkty, ktoré ešte nie sú na Gumroade."""
        from config import PRODUCTS_DIR
        
        if not PRODUCTS_DIR.exists():
            log.warning("Adresár s produktami neexistuje")
            return []
        
        results = []
        product_dirs = [d for d in PRODUCTS_DIR.iterdir() if d.is_dir()]
        
        if not product_dirs:
            log.info("Žiadne produkty v adresári")
            return []
        
        for product_dir in sorted(product_dirs):
            product_name = product_dir.name
            
            # Preskočiť ak je už publikovaný
            if product_name in self._published:
                log.debug(f"⏭️  Už publikovaný: {product_name}")
                continue
            
            log.info(f"Publikujem: {product_name}")
            result = self.publish_product_dir(product_dir)
            if result:
                results.append(result)
        
        return results
    
    def close(self):
        self.client.close()
