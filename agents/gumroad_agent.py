"""
GUMROAD AGENT - PRO VERSION (WITH FOLDER PUBLISHING AND DIRECT FILE UPLOAD)
Nahrává súbory priamo na Gumroad cez multipart/form-data - bez S3 presign hackov.
Podporuje automatické spracovanie adresárov produktov a ochranu pred duplicitami.
"""

import os
import math
import json
import time
import uuid
import logging
import httpx
from pathlib import Path

# Načítanie configu
from config import GUMROAD_ACCESS_TOKEN, PRODUCTS_DIR, PRODUCT_PRICE_USD

log = logging.getLogger("GumroadAgent")

GUMROAD_API = "https://api.gumroad.com/v2"


class GumroadAgent:
    def __init__(self, access_token=None):
        self.token = access_token or GUMROAD_ACCESS_TOKEN
        # Používame jedného klienta s dlhým timeoutom (S3 uploady môžu trvať)
        self.client = httpx.Client(timeout=600.0)
        self.published_log = PRODUCTS_DIR.parent / "logs" / "published.json"
        self._published = self._load_published()

    def _load_published(self) -> dict:
        if self.published_log.exists():
            try:
                return json.loads(self.published_log.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_published(self):
        self.published_log.parent.mkdir(parents=True, exist_ok=True)
        self.published_log.write_text(json.dumps(self._published, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def _build_rich_content(self, manifest: dict, product_name: str, file_id: str) -> list:
        """Gumroad /edit/content tab zobrazuje rich_content (ProseMirror), nie description."""
        mk = manifest.get("marketing", {})
        lead = mk.get("description") or manifest.get("metadata", {}).get("description") or product_name
        hooks = [h for h in mk.get("social_hooks", []) if h][:2]

        blocks = [{"type": "paragraph", "content": [{"type": "text", "text": lead}]}]
        for hook in hooks:
            blocks.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": f"• {hook}"}]
            })
        blocks.append({
            "type": "fileEmbed",
            "attrs": {"id": file_id, "uid": str(uuid.uuid4())}
        })

        return [{
            "title": "Your Download",
            "description": {"type": "doc", "content": blocks}
        }]

    def _attach_rich_content(self, product_id: str, file_id: str,
                             manifest: dict, product_name: str) -> bool:
        """Vyplní Content tab — embed ZIP/DOCX do rich_content stránky."""
        try:
            rich_content = self._build_rich_content(manifest, product_name, file_id)
            log.info(f"Nastavujem rich_content (Content tab) pre produkt {product_id}...")
            res = self.client.put(
                f"{GUMROAD_API}/products/{product_id}",
                json={
                    "access_token": self.token,
                    "rich_content": rich_content,
                    "published": True,
                },
                timeout=30.0,
            )
            res.raise_for_status()
            if res.json().get("success"):
                log.info("✅ Rich content (Content tab) nastavený.")
                return True
            log.warning(f"⚠️ Rich content zlyhal: {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri nastavovaní rich_content: {e}")
        return False

    def _ensure_published(self, product_id: str, url: str) -> None:
        """Zaistí, že produkt je zverejnený (published=true)."""
        try:
            res = self.client.put(
                f"{GUMROAD_API}/products/{product_id}",
                data={
                    "access_token": self.token,
                    "published": "true"
                },
                timeout=30.0
            )
            res.raise_for_status()
            log.info(f"Produkt {product_id} úspešne publikovaný (ensure_published).")
        except Exception as e:
            log.warning(f"⚠️ Nepodarilo sa explicitne publikovať produkt {product_id}: {e}")

    def repair_product_content(self, product_id: str, manifest: dict | None = None,
                               product_name: str = "Product") -> bool:
        """Opraví existujúci produkt — doplní rich_content ak chýba alebo je prázdny."""
        try:
            res = self.client.get(
                f"{GUMROAD_API}/products/{product_id}",
                params={"access_token": self.token},
                timeout=20.0,
            )
            res.raise_for_status()
            product = res.json().get("product", {})
            files = product.get("files") or []
            if not files:
                log.warning(f"Produkt {product_id} nemá žiadne súbory — rich_content sa nedá opraviť.")
                return False

            existing = product.get("rich_content") or []
            if existing:
                log.info(f"Produkt {product.get('name')} už má rich_content ({len(existing)} strán).")
                return True

            name = product.get("name") or product_name
            return self._attach_rich_content(product_id, files[0]["id"], manifest or {}, name)
        except Exception as e:
            log.error(f"Chyba pri repair_product_content: {e}", exc_info=True)
            return False

    def _s3_presign_upload(self, file_path: str) -> str | None:
        """
        Kompletný 3-fázový S3 upload.
        Vracia finálnu internú URL súboru z Gumroadu.
        """
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        # FÁZA 1: Presign
        log.info(f"Fáza 1: S3 Presign pre {filename} ({filesize} B)")
        res1 = self.client.post(f"{GUMROAD_API}/files/presign", data={
            "access_token": self.token,
            "filename": filename,
            "file_size": filesize
        })
        res1.raise_for_status()
        presign_data = res1.json()
        
        # API vráti zoznam častí (parts) a interné ID súboru
        parts = presign_data.get("parts", [])
        upload_id = presign_data.get("upload_id")
        key = presign_data.get("key")
        
        completed_parts = []
        
        # PITFALL: Ak je ZIP príliš malý, Gumroad nevráti "parts", ale rovno jednu S3 URL.
        if not parts and "url" in presign_data:
            log.info("Súbor je malý, Gumroad vrátil priamy S3 link. Nahrávam celý naraz...")
            with open(file_path, "rb") as f:
                s3_res = self.client.put(presign_data["url"], content=f.read(), headers={}) # Pridané headers={}
                s3_res.raise_for_status()
        elif parts:
            log.info(f"Fáza 2: Rozsekávam a nahrávam {len(parts)} častí priamo na S3...")
            chunk_size = math.ceil(filesize / len(parts))
            
            with open(file_path, "rb") as f:
                for part in parts:
                    part_number = part["part_number"]
                    presigned_url = part["presigned_url"]
                    chunk_data = f.read(chunk_size)
                    
                    # AWS S3 vyžaduje striktne PUT požiadavku, žiadne extra hlavičky!
                    s3_res = self.client.put(presigned_url, content=chunk_data, headers={}) # Pridané headers={}
                    s3_res.raise_for_status()
                    etag = s3_res.headers.get("ETag", "").strip('"')
                    completed_parts.append((part_number, etag))
        else:
            raise ValueError(f"Chybná štruktúra Presign JSON: {presign_data}")
            
        # FÁZA 3: Potvrdenie a dokončenie
        log.info("Fáza 3: Potvrdzujem (Complete) na Gumroade...")
        complete_payload = {
            "access_token": self.token,
            "upload_id": upload_id,
            "key": key
        }
        if completed_parts:
            completed_parts.sort(key=lambda x: x[0])
            # Gumroad API očakáva parts[][part_number] a parts[][etag] ako zoznamy
            for i, (pn, et) in enumerate(completed_parts):
                complete_payload[f"parts[][part_number]"] = str(pn)
                complete_payload[f"parts[][etag]"] = et

        res3 = self.client.post(f"{GUMROAD_API}/files/complete", data=complete_payload)
        res3.raise_for_status()
        complete_data = res3.json()
        
        fin_url = complete_data.get("url") or complete_data.get("file_url")
        if not fin_url:
             raise ValueError(f"Complete endpoint nevrátil URL súboru: {complete_data}")
             
        log.info(f"✅ Súbor pripravený v cloude: {fin_url}")
        return fin_url
    
    def _upload_cover_to_catbox(self, cover_path: Path | str) -> str | None:
        """Nahrá cover na Catbox.moe a vráti verejný direct link."""
        cover_path = Path(cover_path)
        if not cover_path.exists():
            return None
        try:
            log.info(f"Nahrávam cover {cover_path.name} na Catbox.moe pre získanie verejného linku...")
            with open(cover_path, "rb") as f:
                res = self.client.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": f},
                    timeout=30.0
                )
            if res.status_code == 200 and res.text.strip().startswith("http"):
                log.info(f"✅ Cover nahratý na Catbox: {res.text.strip()}")
                return res.text.strip()
            log.warning(f"⚠️ Catbox zlyhal ({res.status_code}): {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri Catbox uploade: {e}")
        return None

    def _attach_cover_to_product(self, product_id: str, cover_url: str) -> bool:
        """Priradí cover k produktu cez Gumroad API."""
        try:
            log.info(f"Priraďujem cover k produktu {product_id}...")
            res = self.client.post(
                f"{GUMROAD_API}/products/{product_id}/covers",
                data={"access_token": self.token, "url": cover_url}
            )
            if res.status_code in [200, 201] and res.json().get("success"):
                log.info("✅ Cover priradený!")
                return True
            log.warning(f"⚠️ Priradenie coveru zlyhalo: {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri priraďovaní coveru: {e}")
        return False

    def publish_product_dir(self, product_dir: Path,
                            price: float = PRODUCT_PRICE_USD,
                            cover_path: Path | str | None = None) -> dict | None:
        """
        Publikuje Basic aj Pro verzie produktu ako samostatné položky na Gumroade.
        """
        product_dir = Path(product_dir)
        
        # Ochrana proti duplicite
        if product_dir.name in self._published:
            pub_info = self._published[product_dir.name]
            if "product_id" in pub_info or ("basic" in pub_info and "pro" in pub_info):
                log.warning(f"⏭️ Už publikovaný: {pub_info}")
                return pub_info

        # Zisti cesty k súborom
        pro_dir = product_dir / "v2_PRO_Automation_Kit"
        diy_dir = product_dir / "v1_DIY_Basic"

        zip_file = None
        if pro_dir.exists():
            zip_files = list(pro_dir.glob("*.zip"))
            if zip_files:
                zip_file = zip_files[0]

        docx_file = None
        if diy_dir.exists():
            docx_files = list(diy_dir.glob("*.docx"))
            if docx_files:
                docx_file = docx_files[0]
        if not docx_file and pro_dir.exists():
            docx_files = list(pro_dir.glob("*.docx"))
            if docx_files:
                docx_file = docx_files[0]

        if not zip_file and not docx_file:
            log.warning(f"Žiadny ZIP ani DOCX súbor v {product_dir.name}")
            return None

        # Názov a manifest
        base_product_name = product_dir.name.split("_", 2)[-1].replace("_", " ").title()
        manifest = {}
        data_json = product_dir / "data.json"
        if data_json.exists():
            try:
                manifest = json.loads(data_json.read_text(encoding="utf-8"))
                meta = manifest.get("metadata", {})
                base_product_name = meta.get("title") or manifest.get("title") or base_product_name
            except Exception:
                pass

        # Vypočítaj ceny pre obe verzie
        if price is None:
            price = PRODUCT_PRICE_USD
        else:
            try:
                price = float(price)
            except ValueError:
                price = PRODUCT_PRICE_USD

        # Ochrana pred prehnanými cenami:
        # Horná hranica ceny pre Pro verziu je 14.99 USD, pre Basic verziu 5.99 USD
        pro_price = min(price, 14.99)
        
        # Výpočet ceny pre Basic verziu na základe Pro ceny
        if pro_price >= 12.0:
            basic_price = 4.99
        elif pro_price >= 7.0:
            basic_price = 3.99
        else:
            basic_price = 2.99

        # Nahraj cover na Catbox raz
        catbox_url = None
        actual_cover_path = cover_path or (product_dir / "cover.jpg")
        if actual_cover_path:
            actual_cover_path = Path(actual_cover_path)
            if actual_cover_path.exists():
                catbox_url = self._upload_cover_to_catbox(actual_cover_path)

        result_info = {}

        # 1. NAHRATIE BASIC VERZIE (DOCX)
        if docx_file:
            log.info(f"Nahrávam Basic verziu: {docx_file.name} (${basic_price})...")
            basic_info = self._publish_single_item(
                file_path=docx_file,
                product_name=f"{base_product_name} (Basic Guide)",
                price=basic_price,
                description=self._build_description(manifest, f"{base_product_name} (Basic Guide)"),
                manifest=manifest,
                catbox_url=catbox_url
            )
            if basic_info:
                result_info["basic"] = basic_info

        # 2. NAHRATIE PRO VERZIE (ZIP)
        if zip_file:
            log.info(f"Nahrávam Pro verziu: {zip_file.name} (${pro_price})...")
            pro_info = self._publish_single_item(
                file_path=zip_file,
                product_name=f"{base_product_name} (PRO Automation Kit)",
                price=pro_price,
                description=self._build_description(manifest, f"{base_product_name} (PRO Automation Kit)"),
                manifest=manifest,
                catbox_url=catbox_url
            )
            if pro_info:
                result_info["pro"] = pro_info

        if result_info:
            self._published[product_dir.name] = result_info
            self._save_published()
            return result_info

        return None

    def _publish_single_item(self, file_path: Path, product_name: str, price: float,
                             description: str, manifest: dict, catbox_url: str | None) -> dict | None:
        try:
            file_url = self._s3_presign_upload(str(file_path))
            if not file_url:
                log.error(f"Nepodarilo sa nahrať súbor {file_path.name} cez S3 presign flow.")
                return None

            price_cents = int(price * 100)
            payload = {
                "access_token": self.token,
                "name": product_name,
                "description": description,
                "price": str(price_cents),
                "published": "true",
                "files[][url]": file_url
            }

            res = self.client.post(
                f"{GUMROAD_API}/products",
                data=payload
            )
            res.raise_for_status()
            resp_data = res.json()

            if resp_data.get("success"):
                p_id = resp_data["product"]["id"]
                url = resp_data["product"]["short_url"]

                if catbox_url:
                    self._attach_cover_to_product(p_id, catbox_url)

                product_files = resp_data.get("product", {}).get("files") or []
                if product_files:
                    self._attach_rich_content(p_id, product_files[0]["id"], manifest, product_name)

                self._ensure_published(p_id, url)
                log.info(f"🚀 Úspešne publikované: {product_name} -> {url} (${price})")
                return {"product_id": p_id, "url": url, "price": price}
            else:
                log.error(f"Chyba pri vytváraní položky {product_name}: {resp_data.get('message')}")
        except Exception as e:
            log.error(f"Kritická chyba pri _publish_single_item pre {product_name}: {e}", exc_info=True)
        return None

    def publish_all_pending(self) -> list:
        """Publikuj všetky produkty, ktoré ešte nie sú na Gumroade."""
        if not PRODUCTS_DIR.exists():
            log.warning("Adresár s produktami neexistuje")
            return []

        results = []
        for product_dir in sorted(d for d in PRODUCTS_DIR.iterdir() if d.is_dir()):
            if product_dir.name in self._published:
                log.debug(f"⏭️ Preskočený: {product_dir.name}")
                continue
            log.info(f"Publikujem: {product_dir.name}")
            result = self.publish_product_dir(product_dir)
            if result:
                results.append(result)
        return results

    def close(self):
        self.client.close()