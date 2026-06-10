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

    def _build_description(self, manifest: dict, product_name: str) -> str:
        """Zostaví bohatý, predajný HTML popis z manifestu (marketing + metadata)."""
        meta = manifest.get("metadata", {})
        mk = manifest.get("marketing", {})
        ptype = manifest.get("_meta", {}).get("type", "")

        lead = mk.get("description") or meta.get("description") or f"Premium digital product: {product_name}"
        sub = meta.get("description") if (meta.get("description") and meta.get("description") != lead) else ""
        hooks = [h for h in mk.get("social_hooks", []) if h][:3]

        if ptype == "prompt_pack":
            includes = [
                "🎯 Curated library of high-converting, ready-to-use prompts",
                "📘 Professional strategy guide (DOCX)",
                "🐍 Python helper to run prompts via API",
                "⚙️ One-click setup for Windows &amp; macOS/Linux",
            ]
        else:
            includes = [
                "📘 Step-by-step professional guide (DOCX)",
                "🐍 Ready-to-run Python automation scripts",
                "⚙️ One-click setup (Windows &amp; macOS/Linux)",
                "📄 requirements.txt + README included",
            ]

        parts = [f"<p><strong>{lead}</strong></p>"]
        if sub:
            parts.append(f"<p>{sub}</p>")
        if hooks:
            parts.append("<h3>Why you'll love it</h3><ul>" + "".join(f"<li>{h}</li>" for h in hooks) + "</ul>")
        parts.append("<h3>What's inside</h3><ul>" + "".join(f"<li>{x}</li>" for x in includes) + "</ul>")
        parts.append("<p><em>Instant download · Plug &amp; play · Lifetime access.</em></p>")
        return "".join(parts)

    def publish_product_dir(self, product_dir: Path, price: float = 7.99) -> dict | None:
        # 1. Nájdi hlavný súbor - preferuj PRO ZIP, potom DOCX, potom TXT
        pro_dir = product_dir / "v2_PRO_Automation_Kit"
        diy_dir = product_dir / "v1_DIY_Basic"
        
        # Hľadaj v PRO priečinku najprv
        zip_files = list(pro_dir.glob("*.zip")) if pro_dir.exists() else []
        docx_files = (list(pro_dir.glob("*.docx")) if pro_dir.exists() else []) + \
                     (list(diy_dir.glob("*.docx")) if diy_dir.exists() else []) + \
                     list(product_dir.glob("*.docx"))
        pdf_files = list(product_dir.rglob("*.pdf"))
        txt_files = [f for f in product_dir.rglob("*.txt") if "marketing" not in f.name]
        
        main_file = (zip_files[0] if zip_files else
                     docx_files[0] if docx_files else
                     pdf_files[0] if pdf_files else
                     txt_files[0] if txt_files else None)
        
        if not main_file:
            log.warning(f"Žiadny súbor v {product_dir.name}")
            return None

        # Extrahuj meno produktu + bohatý popis z data.json
        product_name = product_dir.name.split("_", 2)[-1].replace("_", " ").title()
        manifest = {}
        data_json = product_dir / "data.json"
        if data_json.exists():
            try:
                manifest = json.loads(data_json.read_text(encoding="utf-8"))
                meta = manifest.get("metadata", {})
                product_name = meta.get("title") or manifest.get("title") or product_name
            except Exception:
                pass

        description = self._build_description(manifest, product_name)

        log.info(f"Nahrávam {main_file.name} na Gumroad ({product_name})...")

        try:
            with open(main_file, "rb") as f:
                files = {"product[file]": (main_file.name, f, "application/octet-stream")}
                data = {
                    "access_token": self.token,
                    "name": product_name,
                    "price": int(price * 100),
                    "description": description,
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
