import shutil
import os
from pathlib import Path

# Cesty
base_dir = Path(__file__).parent
output_dir = base_dir / "output"
products_dir = output_dir / "products"
logs_dir = output_dir / "logs"

def reset():
    print("Cistim agenta pre novy start...")
    
    # 1. Zmaz cely output adresar
    if output_dir.exists():
        try:
            shutil.rmtree(output_dir)
            print(f"OK: Adresár '{output_dir}' a jeho obsah vymazaný.")
        except Exception as e:
            print(f"ERR pri mazani adresara '{output_dir}': {e}")
    
    # Znovu vytvorime potrebne adresare
    output_dir.mkdir(parents=True, exist_ok=True)
    products_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    print("OK: Adresáre 'output', 'products' a 'logs' znovu vytvorené.")

    # 2. Zmaz root-level CSV, DB, TXT správy a dočasné súbory
    files_to_remove = [
        "seo_report.db",
        "seo_report.csv",
        "leads.csv",
        "results.csv",
        "gpt_interactions.csv",
        "notion_clients.json",
        "notion_os.json",
        "optimized_prompts.json",
        "prompt_optimization_results.json",
        "seo_reports.json",
    ]

    for filename in files_to_remove:
        f_path = base_dir / filename
        if f_path.exists():
            try:
                f_path.unlink()
                print(f"OK: Súbor '{filename}' vymazaný.")
            except Exception as e:
                print(f"ERR pri mazaní súboru '{filename}': {e}")

    # Mazanie vzorovaných reportov (napr. seo_report_*.txt alebo *.csv)
    for p in base_dir.glob("seo_report_*.*"):
        if p.is_file():
            try:
                p.unlink()
                print(f"OK: Vzorovaný report '{p.name}' vymazaný.")
            except Exception:
                pass

    # 3. Zmaz __pycache__
    for p in base_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(p)
        except Exception:
            pass

    print("\nReset dokonceny. Mozes spustit agenta!")

if __name__ == "__main__":
    reset()