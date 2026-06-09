import json
import logging
from pathlib import Path
from agents.file_agent import FileAgent

# Nastavenie loggingu
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("FixDOCX")

def fix_all():
    base_dir = Path(__file__).parent
    products_dir = base_dir / "output" / "products"
    
    if not products_dir.exists():
        print("❌ Priečinok s produktmi neexistuje.")
        return

    agent = FileAgent()
    
    # Prejdi všetky podadresáre v products
    product_folders = [d for d in products_dir.iterdir() if d.is_dir()]
    
    if not product_folders:
        print("❌ Nenašli sa žiadne priečinky s produktmi.")
        return

    print(f"🔧 Opravujem DOCX pre {len(product_folders)} produktov...")

    for folder in product_folders:
        json_path = folder / "data.json"
        if not json_path.exists():
            continue
            
        try:
            # 1. Načítaj existujúce dáta
            product = json.loads(json_path.read_text(encoding="utf-8"))
            
            # 2. Použijeme metódu save, aby sme vytvorili celú štruktúru v1/v2 a nové DOCX
            print(f"  -> Regenerujem kompletný balík pre: {product.get('title')}")
            agent.save(product)
            
        except Exception as e:
            print(f"  ❌ Chyba v {folder.name}: {e}")

    print("\n✅ Hotovo! Všetky produkty boli pregenerované do v1/v2 balíkov s novými DOCX.")

if __name__ == "__main__":
    fix_all()
