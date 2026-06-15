# test_gumroad_upload.py
import httpx
import os
import urllib.parse
import math
import logging

# Nastavenie logovania pre lepšiu viditeľnosť
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("GumroadTest")

# Načítanie tokenu z .env súboru
try:
    with open(r"C:\Users\jangr\passive_agent\.env", "r") as f:
        for line in f:
            if "GUMROAD_ACCESS_TOKEN" in line:
                TOKEN = line.split("=", 1)[1].strip()
                break
    if not TOKEN:
        raise ValueError("GUMROAD_ACCESS_TOKEN not found in .env")
except FileNotFoundError:
    log.error("Súbor .env nebol nájdený. Uistite sa, že existuje a obsahuje GUMROAD_ACCESS_TOKEN.")
    exit(1)
except ValueError as e:
    log.error(e)
    exit(1)

# ID existujúceho produktu na Gumroade, ku ktorému chceme pridať súbor
# TOTO ID MUSÍ BYŤ PLATNÉ A EXISTUJÚCE NA VAŠOM GUMROAD ÚČTE!
# Získajte ho z URL produktu na Gumroade (napr. gumroad.com/l/YOUR_PRODUCT_ID)
PRODUCT_ID_RAW = "hscow==" # Nahraďte skutočným ID produktu
PRODUCT_ID_ENC = urllib.parse.quote(PRODUCT_ID_RAW, safe="")

# Cesta k ZIP súboru, ktorý chcete nahrať
ZIP_PATH = r"C:\Users\jangr\passive_agent\output\products\20260615_211238_ai_prompt_engineering_automation_kit_for\v2_PRO_Automation_Kit\ai_prompt_engineering_automation_kit_for_Guide_PRO_Kit.zip"
# Cesta k cover obrázku (ak ho chcete nahrať/aktualizovať)
COVER_PATH = r"C:\Users\jangr\passive_agent\output\products\20260614_123532_plug_play_automation_kit_python_scripts\cover.jpg"


GUMROAD_API = "https://api.gumroad.com/v2"

def s3_presign_upload_standalone(file_path: str, access_token: str) -> str | None:
    """
    Kompletný 3-fázový S3 upload pre Gumroad.
    Vracia finálnu internú URL súboru z Gumroadu.
    """
    filename = os.path.basename(file_path)
    filesize = os.path.getsize(file_path)
    
    client = httpx.Client(timeout=600.0) # Samostatný klient pre túto funkciu
    
    try:
        # FÁZA 1: Presign
        log.info(f"Fáza 1: S3 Presign pre {filename} ({filesize} B)")
        res1 = client.post(f"{GUMROAD_API}/files/presign", data={
            "access_token": access_token,
            "filename": filename,
            "file_size": filesize
        })
        res1.raise_for_status()
        presign_data = res1.json()
        
        parts = presign_data.get("parts", [])
        upload_id = presign_data.get("upload_id")
        key = presign_data.get("key")
        
        completed_parts = []
        
        if not parts and "url" in presign_data: # Malý súbor, priamy S3 link
            log.info("Súbor je malý, Gumroad vrátil priamy S3 link. Nahrávam celý naraz...")
            with open(file_path, "rb") as f:
                s3_res = client.put(presign_data["url"], content=f.read(), headers={})
                s3_res.raise_for_status()
        elif parts: # Väčší súbor, multipart upload
            log.info(f"Fáza 2: Rozsekávam a nahrávam {len(parts)} častí priamo na S3...")
            chunk_size = math.ceil(filesize / len(parts))
            
            with open(file_path, "rb") as f:
                for part in parts:
                    part_number = part["part_number"]
                    presigned_url = part["presigned_url"]
                    chunk_data = f.read(chunk_size)
                    
                    s3_res = client.put(presigned_url, content=chunk_data, headers={})
                    s3_res.raise_for_status()
                    etag = s3_res.headers.get("ETag", "").strip('"')
                    completed_parts.append((part_number, etag))
        else:
            raise ValueError(f"Chybná štruktúra Presign JSON: {presign_data}")
            
        # FÁZA 3: Potvrdenie a dokončenie
        log.info("Fáza 3: Potvrdzujem (Complete) na Gumroade...")
        complete_payload = {
            "access_token": access_token,
            "upload_id": upload_id,
            "key": key
        }
        if completed_parts:
            completed_parts.sort(key=lambda x: x[0])
            for i, (pn, et) in enumerate(completed_parts):
                complete_payload[f"parts[][part_number]"] = str(pn)
                complete_payload[f"parts[][etag]"] = et

        res3 = client.post(f"{GUMROAD_API}/files/complete", data=complete_payload)
        res3.raise_for_status()
        complete_data = res3.json()
        
        fin_url = complete_data.get("url") or complete_data.get("file_url")
        if not fin_url:
             raise ValueError(f"Complete endpoint nevrátil URL súboru: {complete_data}")
             
        log.info(f"✅ Súbor pripravený v cloude: {fin_url}")
        return fin_url
    except Exception as e:
        log.error(f"Chyba pri S3 presign uploade pre {filename}: {e}", exc_info=True)
        return None
    finally:
        client.close()


def upload_product_file_and_cover_to_existing_product(product_id: str, zip_path: str, cover_path: str, access_token: str):
    log.info(f"Pokúšam sa nahrať súbor a cover k existujúcemu produktu ID: {product_id}")

    # 1. Nahraj ZIP súbor cez S3 presign flow
    zip_gumroad_url = s3_presign_upload_standalone(zip_path, access_token)
    if not zip_gumroad_url:
        log.error("Nepodarilo sa nahrať ZIP súbor.")
        return

    # 2. Nahraj cover obrázok na Catbox.moe (pretože Gumroad API pre cover je zložitejšie)
    cover_catbox_url = None
    if os.path.exists(cover_path):
        try:
            log.info(f"Nahrávam cover {os.path.basename(cover_path)} na Catbox.moe pre získanie verejného linku...")
            with httpx.Client(timeout=30.0) as client:
                with open(cover_path, "rb") as f:
                    res = client.post(
                        "https://catbox.moe/user/api.php",
                        data={"reqtype": "fileupload"},
                        files={"fileToUpload": f},
                    )
                if res.status_code == 200 and res.text.strip().startswith("http"):
                    cover_catbox_url = res.text.strip()
                    log.info(f"✅ Cover nahratý na Catbox: {cover_catbox_url}")
                else:
                    log.warning(f"⚠️ Nahratie na Catbox zlyhalo s kódom {res.status_code}: {res.text}")
        except Exception as e:
            log.warning(f"⚠️ Výnimka pri nahrávaní coveru na Catbox: {e}", exc_info=True)
    else:
        log.warning(f"Cover súbor neexistuje: {cover_path}")

    # 3. Aktualizuj existujúci produkt na Gumroade
    update_payload = {
        "access_token": access_token,
        "files[][url]": zip_gumroad_url, # Pridanie hlavného súboru
    }
    if cover_catbox_url:
        update_payload["thumbnail_url"] = cover_catbox_url # Pridanie coveru

    try:
        log.info(f"Aktualizujem produkt {product_id} s novými súbormi...")
        with httpx.Client(timeout=60.0) as client:
            res = client.put(
                f"{GUMROAD_API}/products/{product_id}",
                data=update_payload
            )
        res.raise_for_status()
        resp_data = res.json()

        if resp_data.get("success"):
            log.info(f"✅ ÚSPECH! Produkt {product_id} bol úspešne aktualizovaný.")
            log.info(f"Produkt URL: {resp_data['product']['short_url']}")
        else:
            log.error(f"❌ Chyba pri aktualizácii produktu: {resp_data.get('message')} | {resp_data.get('errors')}")
    except Exception as e:
        log.error(f"Kritická chyba pri aktualizácii produktu {product_id}: {e}", exc_info=True)


if __name__ == "__main__":
    print(f"Raw ID:  {PRODUCT_ID_RAW}")
    print(f"Enc ID:  {PRODUCT_ID_ENC}")
    print(f"ZIP Path: {ZIP_PATH}")
    print(f"Cover Path: {COVER_PATH}")

    if not os.path.exists(ZIP_PATH):
        log.error(f"ZIP súbor nebol nájdený na ceste: {ZIP_PATH}")
        exit(1)

    # Zavoláme funkciu na upload a aktualizáciu
    upload_product_file_and_cover_to_existing_product(PRODUCT_ID_ENC, ZIP_PATH, COVER_PATH, TOKEN)
