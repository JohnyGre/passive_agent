"""
GUMROAD AGENT - PRO VERSION (WITH FOLDER PUBLISHING AND S3 MULTIPART UPLOADS)
Rieši AWS S3 Presign Multipart Upload pre veľké ZIP súbory, aby sme obišli limity Gumroad API.
Podporuje automatické spracovanie adresárov produktov a ochranu pred duplicitami.
"""

import os
import math
import json
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
                s3_res = self.client.put(presign_data["url"], content=f.read(), headers={})
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
                    s3_res = self.client.put(presigned_url, content=chunk_data, headers={})
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
            if res.status_code == 200:
                url = res.text.strip()
                if url.startswith("http"):
                    log.info(f"✅ Cover úspešne nahratý na Catbox: {url}")
                    return url
            log.warning(f"⚠️ Nahratie na Catbox zlyhalo s kódom {res.status_code}: {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri nahrávaní na Catbox: {e}")
        return None

    def _attach_cover_to_product(self, product_id: str, cover_url: str) -> bool:
        """Priradí cover k produktu cez Gumroad API."""
        try:
            log.info(f"Priraďujem cover URL k produktu {product_id}...")
            res = self.client.post(
                f"{GUMROAD_API}/products/{product_id}/covers",
                data={
                    "access_token": self.token,
                    "url": cover_url
                }
            )
            if res.status_code in [200, 201]:
                data = res.json()
                if data.get("success"):
                    log.info("✅ Cover úspešne priradený k produktu!")
                    return True
            log.warning(f"⚠️ Priradenie coveru zlyhalo: {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri priraďovaní coveru: {e}")
        return False

    def publish_product_dir(self, product_dir: Path,
                            price: float = PRODUCT_PRICE_USD,
                            cover_path: Path | str | None = None) -> dict | None:
        """
        Publikuje produkt z lokálneho adresára, automaticky vyhľadá a nahrá
        hlavný ZIP/súbor cez S3 a prípadný cover.
        """
        product_dir = Path(product_dir)
        
        # Ochrana proti duplicite
        if product_dir.name in self._published:
            log.warning(f"⏭️ Už publikovaný: {self._published[product_dir.name]}")
            return self._published[product_dir.name]

        # 1. Nájdi hlavný súbor - preferuj PRO ZIP, potom Basic ZIP, potom DOCX, potom PDF, potom TXT
        pro_dir = product_dir / "v2_PRO_Automation_Kit"
        diy_dir = product_dir / "v1_DIY_Basic"

        main_file = None
        if pro_dir.exists():
            zip_files = list(pro_dir.glob("*.zip"))
            if zip_files:
                main_file = zip_files[0]
            else:
                docx_files = list(pro_dir.glob("*.docx"))
                if docx_files:
                    main_file = docx_files[0]
        
        if not main_file and diy_dir.exists():
            docx_files = list(diy_dir.glob("*.docx"))
            if docx_files:
                main_file = docx_files[0]

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
            # 1. Najskôr prepasírujeme ZIP/súbor cez S3
            file_url = self._s3_presign_upload(str(main_file))
            if not file_url:
                log.error(f"Nepodarilo sa nahrať hlavný súbor {main_file.name} cez S3 presign flow.")
                return None

            # 2. Cena musí byť v centoch
            if price is None:
                price = PRODUCT_PRICE_USD
            else:
                try:
                    price = float(price)
                except ValueError:
                    price = PRODUCT_PRICE_USD
            price_cents = int(price * 100)

            # 3. Payload pre vytvorenie produktu
            payload = {
                "access_token": self.token,
                "name": product_name,
                "description": description,
                "price": str(price_cents),
                "published": "true",
                "files[][url]": file_url
            }

            # 4. Príprava Cover obrázku (ak je k dispozícii) - UPLOAD NA CATBOX
            catbox_url = None
            actual_cover_path = cover_path or (product_dir / "cover.jpg")
            if actual_cover_path:
                actual_cover_path = Path(actual_cover_path)
                if actual_cover_path.exists():
                    catbox_url = self._upload_cover_to_catbox(actual_cover_path)
                    # NEPRIDÁVAJ thumbnail_url do počiatočného payloadu

            log.info(f"Vytváram finálny produkt '{product_name}' s priradeným súborom "
                     f"(a coverom, ak bude priradený)...")
            
            res = self.client.post(
                f"{GUMROAD_API}/products",
                data=payload
            )
            res.raise_for_status()

            resp_data = res.json()
            if resp_data.get("success"):
                p_id = resp_data["product"]["id"]
                url = resp_data["product"]["short_url"]

                # 5. Priradenie coveru po vytvorení produktu
                if catbox_url:
                    self._attach_cover_to_product(p_id, catbox_url)

                log.info(f"🚀 ÚSPECH! Produkt vytvorený a súbory nahrané: {url}")

                result = {"product_id": p_id, "url": url}
                self._published[product_dir.name] = result
                self._save_published()
                return result
            else:
                err_msg = resp_data.get('message', 'Unknown error')
                log.error(f"❌ Chyba pri finalizácii produktu: {err_msg}")
                if resp_data.get('errors'):
                    log.error(f"Detaily: {resp_data['errors']}")
                return None

        except Exception as e:
            log.error(f"Kritická chyba v GumroadAgentovi pri publish_product_dir: {e}", exc_info=True)
            return None

    def publish_all_pending(self) -> list:
        """Publikuj všetky produkty, ktoré ešte nie sú na Gumroade."""
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
                log.debug(f"⏭️  Už publikovaný: {self._published[product_dir.name]}")
                continue

            log.info(f"Publikujem: {product_name}")
            # Tu by sme potrebovali cover_path, ak by sa volalo publish_all_pending
            # Pre jednoduchosť to zatiaľ necháme tak, keďže sa zameriavame na job_generate_products
            result = self.publish_product_dir(product_dir)
            if result:
                results.append(result)

        return results

    def close(self):
        self.client.close()
