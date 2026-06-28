"""
GUMROAD UPLOAD - Jednoduchý script na nahratie produktu
"""
import json
import os
import sys

# Pridáme cestu pre import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.gumroad_agent import GumroadAgent
from config import GUMROAD_ACCESS_TOKEN, PRODUCT_PRICE_USD

def main():
    # Cesty
    product_dir = "output/products/20260610_221207_notion_operating_system_for_freelancers"
    cover_path = os.path.join(product_dir, "cover.jpg")
    
    # Načítame data.json pre názov a popis
    with open(os.path.join(product_dir, "data.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    
    price = data["_meta"].get("suggested_price", PRODUCT_PRICE_USD)
    
    print(f"💰 Cena: ${price}")
    print(f"📁 Produktový adresár: {product_dir}")
    print(f"🖼️  Cover: {cover_path}")
    
    # Upload
    agent = GumroadAgent(GUMROAD_ACCESS_TOKEN)
    result = agent.publish_product_dir(
        product_dir=product_dir,
        price=price,
        cover_path=cover_path
    )
    
    if result:
        print(f"\n✅ ÚSPECH! Produkt(y) nahraný:")
        for version, info in result.items():
            if "url" in info:
                print(f"🔗 {version.capitalize()} verzia: {info['url']}")
    else:
        print(f"\n❌ CHYBA pri uploade!")
    
    agent.close()
    return result

if __name__ == "__main__":
    main()