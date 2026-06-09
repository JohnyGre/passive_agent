import httpx
import json
import logging
from agents.content_agent import ContentAgent
from config import OLLAMA_URL

# Nastavenie logovania pre lepšiu viditeľnosť
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("OllamaJsonTest")

def run_ollama_json_test():
    log.info("Spúšťam testovanie Ollama modelov pre generovanie JSON...")

    test_topic = "How to create a passive income stream with AI"
    test_product_type = "mini_guide"

    # 1. Získanie zoznamu dostupných Ollama modelov
    available_models = []
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=60.0)
        response.raise_for_status()
        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]
        log.info(f"Nájdené Ollama modely: {available_models}")
    except httpx.RequestError as e:
        log.error(f"Nepodarilo sa pripojiť k Ollama serveru na {OLLAMA_URL}: {e}")
        log.info("Uistite sa, že Ollama server beží a je dostupný.")
        return
    except json.JSONDecodeError:
        log.error(f"Nepodarilo sa parsovať odpoveď z {OLLAMA_URL}/api/tags ako JSON.")
        return

    if not available_models:
        log.warning("Na Ollama serveri neboli nájdené žiadne modely. Ukončujem test.")
        return

    results = {}
    agent = ContentAgent()

    for model_name in available_models:
        log.info(f"\n--- Testujem model: {model_name} ---")
        try:
            # Používame ollama_model_override pre testovanie konkrétneho modelu
            generated_content = agent.generate(
                topic=test_topic,
                product_type=test_product_type,
                ollama_model_override=model_name
            )

            if generated_content and not generated_content.get("_meta", {}).get("parse_failed"):
                log.info(f"Model {model_name}: ÚSPEŠNE vygeneroval a parsoval JSON.")
                results[model_name] = "SUCCESS"
                # Voliteľné: môžete tu pridať ďalšie overenia štruktúry JSON
            else:
                log.error(f"Model {model_name}: ZLYHAL pri generovaní alebo parsovaní JSON.")
                results[model_name] = "FAILED"
                if generated_content:
                    log.error(f"Surový výstup (časť): {generated_content.get('raw_content', '')[:500]}...")
        except Exception as e:
            log.error(f"Model {model_name}: Vyskytla sa neočakávaná chyba: {e}")
            results[model_name] = f"ERROR: {e}"
    
    agent.close()

    log.info("\n--- SÚHRN VÝSLEDKOV ---")
    for model, status in results.items():
        log.info(f"Model: {model:<30} Status: {status}")

    log.info("\nTestovanie dokončené.")

if __name__ == "__main__":
    run_ollama_json_test()
