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
    
    # 1. Zmaz vygenerovane produkty
    if products_dir.exists():
        try:
            shutil.rmtree(products_dir)
            products_dir.mkdir(parents=True)
            print("OK: Priečinok produktov vymazaný.")
        except Exception as e:
            print(f"ERR pri mazani produktov: {e}")

    # 2. Zmaz logy
    if logs_dir.exists():
        for item in logs_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                except Exception as e:
                    print(f"ERR: Nemôžem zmazať {item.name}: {e}")
        print("OK: Logy a historia vymazane.")

    # 3. Zmaz __pycache__
    for p in base_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(p)
        except Exception:
            pass

    print("\nReset dokonceny. Mozes spustit agenta!")

if __name__ == "__main__":
    reset()
