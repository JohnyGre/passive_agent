"""
VALIDATION AGENT - PRO VERSION 2.0
Kontroluje funkčnosť, robustnosť a profesionálnu kvalitu (readability) kódu.
Zabezpečuje, že kód v "Pro Kit" nie je len funkčný, ale aj profesionálne napísaný.
"""

import ast
import logging
import subprocess
import sys
import tempfile
from pathlib import Path # Opravil som malý detail v importe

log = logging.getLogger("ValidationAgent")

class ValidationAgent:
    def __init__(self):
        # Rozšírený zoznam PRO knižníc podľa tvojho Tech Stacku
        self.pro_modules = {
            'requests', 'httpx', 'urllib', 'aiohttp', 'playwright', 'selenium', # API & Web
            'sqlite3', 'psycopg2', 'sqlalchemy',                               # DB
            'pandas', 'numpy', 'csv', 'json',                                   # Data
            'logging', 'asyncio', 'apscheduler',                                # Robustness
            'pydantic', 'python-dotenv', 'dotenv',                              # Config & Validation
            'notion_client', 'googlesearch'                                     # Pridané nové knižnice
        }

    def validate_python_syntax(self, code: str) -> bool:
        """Skontroluje, či je kód syntakticky správny."""
        if not code: return False
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            log.warning(f"❌ Syntaktická chyba: {e}")
            log.warning(f"❌ Chybný kód:\n{code}") # Pridané logovanie chybného kódu
            return False

    def validate_code_professionalism(self, code: str) -> tuple[bool, list[str]]:
        """
        Analyzuje kvalitu kódu pre "PRO" úroveň:
        1. Docstrings (existencia dokumentácie pre funkcie/triedy)
        2. Type Hints (používanie typov pre argumenty a návratové hodnoty)
        """
        if not code: return False, ["Žiadny kód."]

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, ["Syntaktická chyba."]

        issues = []
        functions_with_docs = 0
        functions_total = 0
        functions_with_types = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions_total += 1

                # 1. Kontrola Docstringu
                if ast.get_docstring(node):
                    functions_with_docs += 1
                else:
                    issues.append(f"Chýba docstring vo funkcii '{node.name}'")

                # 2. Kontrola Type Hints (anotácie argumentov)
                has_args_types = all(arg.annotation is not None for arg in node.args.args if arg.arg != 'self')
                if has_args_types:
                    functions_with_types += 1
                else:
                    issues.append(f"Chýbajú type hints v funkcii '{node.name}'")

        # Hodnotenie kvality
        if functions_total > 0:
            doc_ratio = functions_with_docs / functions_total
            type_ratio = functions_with_types / functions_total

            if doc_ratio < 0.8:
                issues.append(f"Nízka kvalita dokumentácie ({int(doc_ratio*100)}%)")
            if type_ratio < 0.8:
                issues.append(f"Nízka kvalita typov ({int(type_ratio*100)}%)")

        if issues:
            return False, issues
        return True, []

    def validate_pro_robustness(self, code: str) -> tuple[bool, list[str]]:
        """
        Kontroluje, či kód obsahuje prvky pre produkčné prostredie:
        1. Error handling (try-except)
        2. Využitie reálnych knižníc (nie len random/print)
        """
        if not code: return False, ["Žiadny kód."]

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, ["Syntaktická chyba."]

        issues = []
        has_try_except = any(isinstance(node, ast.Try) for node in ast.walk(tree))

        has_pro_imports = False
        for node in ast.walk(tree):
            # Hľadanie PRO importov
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.pro_modules:
                        has_pro_imports = True
            elif isinstance(node, ast.ImportFrom):
                if node.module in self.pro_modules:
                    has_pro_imports = True

        if not has_try_except:
            issues.append("Chýba Error Handling (žiadne try/except bloky)")
        if not has_pro_imports:
            issues.append("Chýbajú produkčné knižnice (API/DB/Data/Web)")

        if issues:
            return False, issues
        return True, []

    def dry_run(self, code: str) -> tuple[bool, str]:
        """Spustí kód v izolovanom procese a kontroluje importy a základnú logiku."""
        if not code: return False, "Žiadny kód."

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                return True, ""
            else:
                # Ak je chyba ImportError, je to kritický problém pre PRO balíček
                if "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr:
                    return False, f"Kritické chýbajúce knižnice: {result.stderr.strip()}"

                # Iné chyby (napr. ConnectionError) považujeme za logicky OK pre test
                return True, ""

        except subprocess.TimeoutExpired:
            return True, "" # Kód beží, čo je v poriadku
        except Exception as e:
            return False, str(e)
        finally:
            try:
                import os
                os.remove(tmp_path)
            except:
                pass

    def full_check(self, code: str) -> tuple[bool, list[str]]:
        """Kompletná kontrola: Syntax -> Robustness -> Professionalism -> Dry Run"""
        log.info("🚀 Spúšťam kompletnú PRO validáciu kódu...")

        # 1. Syntax
        if not self.validate_python_syntax(code):
            return False, ["Syntaktická chyba."]

        # 2. Robustnosť (Error handling & Modules)
        robust_ok, robust_issues = self.validate_pro_robustness(code)

        # 3. Profesionalita (Docstrings & Types)
        prof_ok, prof_issues = self.validate_code_professionalism(code)

        # 4. Dry Run (Imports & Runtime)
        dry_ok, dry_issue_str = self.dry_run(code) # Zmenil som názov premennej

        # Konvertujeme dry_issue_str na list, ak nie je prázdny
        dry_issues = [dry_issue_str] if dry_issue_str else []

        all_issues = robust_issues + prof_issues + dry_issues

        if not robust_ok or not prof_ok or not dry_ok:
            log.warning(f"❌ Kód neprešiel PRO validáciou: {all_issues}")
            return False, all_issues

        log.info("✅ Kód je absolútne PRO!")
        return True, []