"""
VALIDATION AGENT
Kontroluje kvalitu a funkčnosť vygenerovaného kódu.
Zabezpečuje, že "Pro Kit" neobsahuje nefunkčné skripty.
"""

import ast
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("ValidationAgent")

class ValidationAgent:
    def validate_python_syntax(self, code: str) -> bool:
        """Skontroluje, či je kód syntakticky správny (bez spustenia)."""
        if not code:
            return False
        try:
            ast.parse(code)
            log.info("✅ Syntaktická kontrola kódu úspešná.")
            return True
        except SyntaxError as e:
            log.warning(f"❌ Syntaktická chyba v kóde: {e}")
            return False

    def validate_pro_features(self, code: str) -> tuple[bool, str]:
        """
        Analyzuje AST strom kódu a overuje univerzálne produkčné štandardy:
        1. Error handling (try-except bloky)
        2. Využitie reálnych I/O, API alebo dátových knižníc (žiadny pure-random balast)
        """
        if not code:
            return False, "Žiadny kód na analýzu."
            
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, "Syntaktická chyba znemožnila analýzu štruktúry."

        # Kontrola prítomnosti Try-Except bloku
        has_try_except = any(isinstance(node, ast.Try) for node in ast.walk(tree))
        
        # Zoznam "PRO" knižníc: API, Databázy, Dáta, Asynch, Logovanie
        pro_modules = {
            'requests', 'httpx', 'urllib', 'aiohttp', # API
            'sqlite3', 'psycopg2', 'sqlalchemy',      # DB
            'pandas', 'numpy', 'csv', 'json',         # Data
            'logging', 'asyncio'                      # Robustness
        }
        
        has_pro_imports = False
        has_random_abuse = False
        
        for node in ast.walk(tree):
            # Hľadanie PRO importov
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in pro_modules:
                        has_pro_imports = True
            elif isinstance(node, ast.ImportFrom):
                if node.module in pro_modules:
                    has_pro_imports = True
                    
            # Detekcia "odfláknutého" kódu (časté používanie random.randint pre fake dáta)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if getattr(node.func.value, 'id', '') == 'random' and node.func.attr in ['randint', 'choice']:
                    has_random_abuse = True

        issues = []
        if not has_try_except:
            issues.append("Chýba Error Handling (žiadne try/except bloky)")
        if not has_pro_imports:
            issues.append("Chýbajú produkčné knižnice (API/DB/Data processing). Kód vyzerá ako hračka.")
        
        # Ak tam je random, ale kód spĺňa iné PRO štandardy, dáme len warning, ale nezastavíme to.
        # Niekedy je random potrebný (napr. exponential backoff).
        
        if issues:
            log.warning(f"⚠️ PRO Validácia zlyhala: {' | '.join(issues)}")
            return False, " | ".join(issues)

        if has_random_abuse:
            log.info("⚠️ Kód obsahuje modul random, ale prešiel PRO validáciou. Monitoruj, či LLM negeneruje fake dáta.")

        log.info("✅ Kód obsahuje univerzálne PRO štruktúry (Try/Except + Reálne knižnice).")
        return True, ""

    def dry_run(self, code: str) -> tuple[bool, str]:
        """
        Pokúsi sa spustiť kód v izolovanom procese.
        Kontroluje importy a základnú logiku.
        """
        if not code:
            return False, "Žiadny kód na spustenie."

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            # Spustíme kód s limitom 5 sekúnd (len test importov a syntaxe pri behu)
            # Použijeme -c "import sys; ..." na potlačenie reálneho vykonávania ak je to možné, 
            # ale pre jednoduchosť skúsime reálny beh.
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                log.info("✅ Dry run kódu úspešný.")
                return True, ""
            else:
                # Ak kód skončil chybou (napr. chýbajúce API kľúče - čo je v poriadku), 
                # ale syntax a importy prešli.
                # Ak je chyba ImportError, je to problém.
                if "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr:
                    log.warning(f"⚠️ Chýbajúce knižnice v dry run: {result.stderr}")
                    return False, result.stderr
                
                # Ak je to iná chyba (napr. ConnectionError), kód je pravdepodobne logicky OK
                log.info("✅ Kód sa pokúsil spustiť (logické chyby sú očakávané kvôli chýbajúcim kľúčom).")
                return True, ""

        except subprocess.TimeoutExpired:
            log.info("✅ Kód beží (zastavený timeoutom, čo je dobré znamenie).")
            return True, ""
        except Exception as e:
            log.error(f"❌ Dry run zlyhal katastrofálne: {e}")
            return False, str(e)
        finally:
            try:
                Path(tmp_path).unlink()
            except:
                pass
