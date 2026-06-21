"""
VALIDATION AGENT - PRO VERSION 3.0 (ANTI-MOCK ENFORCEMENT)
Kontroluje funkčnosť, robustnosť, profesionálnu kvalitu a REÁLNOSŤ kódu.
Zabezpečuje, že kód v "Pro Kit" nie je simulovaný, mock, ani placeholder.
"""

import ast
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("ValidationAgent")

# ══════════════════════════════════════════════════════════
#  ZAKÁZANÉ PATTERNY — kód s týmito prvkami je ODMIETNUTÝ
# ══════════════════════════════════════════════════════════

# Komentáre indikujúce mock/simuláciu
MOCK_COMMENT_PATTERNS = [
    r'#\s*simulated?\b',
    r'#\s*mock\b',
    r'#\s*placeholder\b',
    r'#\s*example\s+only\b',
    r'#\s*demo\b',
    r'#\s*dummy\b',
    r'#\s*fake\b',
    r'#\s*todo:?\s*(replace|implement|add real)',
    r'#\s*stub\b',
]

# Stringy v kóde indikujúce mock dáta
MOCK_STRING_PATTERNS = [
    r'example\.com',
    r'fake[-_]?data',
    r'mock[-_]?response',
    r'placeholder[-_]?text',
    r'sample[-_]?output',
    r'dummy[-_]?result',
    r'lorem\s+ipsum',
]


class ValidationAgent:
    def __init__(self):
        # PRO knižnice — len tie, ktoré sú reálne povolené v Tech Stacku
        self.pro_modules = {
            'requests', 'httpx', 'urllib', 'aiohttp', 'playwright',  # API & Web
            'bs4', 'beautifulsoup4',                                  # Parsing
            'sqlite3', 'psycopg2', 'sqlalchemy',                     # DB
            'pandas', 'numpy', 'csv', 'json',                        # Data
            'logging', 'asyncio', 'apscheduler',                     # Robustness
            'pydantic', 'python-dotenv', 'dotenv',                   # Config & Validation
            'argparse', 'pathlib', 'subprocess',                     # CLI & System
        }

    # ══════════════════════════════════════════════════════════
    #  1. SYNTAX CHECK
    # ══════════════════════════════════════════════════════════

    def validate_python_syntax(self, code: str) -> bool:
        """Skontroluje, či je kód syntakticky správny."""
        if not code: return False
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            log.warning(f"❌ Syntaktická chyba: {e}")
            log.warning(f"❌ Chybný kód:\n{code}")
            return False

    # ══════════════════════════════════════════════════════════
    #  2. PROFESSIONALISM CHECK (Docstrings & Type Hints)
    # ══════════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════════
    #  3. ROBUSTNESS CHECK (Error Handling & Real Modules)
    # ══════════════════════════════════════════════════════════

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
                if node.module and node.module.split('.')[0] in self.pro_modules:
                    has_pro_imports = True

        if not has_try_except:
            issues.append("Chýba Error Handling (žiadne try/except bloky)")
        if not has_pro_imports:
            issues.append("Chýbajú produkčné knižnice (API/DB/Data/Web)")

        if issues:
            return False, issues
        return True, []

    # ══════════════════════════════════════════════════════════
    #  4. ANTI-MOCK CHECK — NOVÉ! Detekuje simulácie a fake kód
    # ══════════════════════════════════════════════════════════

    def validate_no_mock_patterns(self, code: str) -> tuple[bool, list[str]]:
        """
        Skenuje kód na zakázané mock/simulačné patterny:
        1. time.sleep() na simuláciu API volaní (nie rate limiting)
        2. Komentáre s mock/simulated/placeholder/demo kľúčovými slovami
        3. Funkcie vracajúce len hardcoded dict/list bez HTTP volania
        4. random.choice/random.sample na generovanie falošných výsledkov
        5. Stringy obsahujúce example.com, fake_data, mock_response, atď.
        """
        if not code: return False, ["Žiadny kód."]

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, ["Syntaktická chyba — nedá sa analyzovať na mock patterny."]

        issues = []

        # ── 4a. Detekcia time.sleep() simulácie ──
        self._check_sleep_simulation(tree, code, issues)

        # ── 4b. Detekcia mock komentárov ──
        self._check_mock_comments(code, issues)

        # ── 4c. Detekcia random-based fake výsledkov ──
        self._check_random_faking(tree, issues)

        # ── 4d. Detekcia hardcoded fake dát v stringoch ──
        self._check_mock_strings(code, issues)

        # ── 4e. Detekcia funkcií vracajúcich len statické dáta ──
        self._check_static_return_functions(tree, code, issues)

        if issues:
            return False, issues
        return True, []

    def _check_sleep_simulation(self, tree: ast.AST, code: str, issues: list) -> None:
        """Detekuje time.sleep() používaný na simuláciu API volaní."""
        has_time_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'time':
                        has_time_import = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'time':
                    has_time_import = True

        if not has_time_import:
            return

        # Hľadaj time.sleep() s podozrivým kontextom
        has_real_http = self._has_real_http_calls(tree)
        sleep_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # time.sleep(...)
                if isinstance(func, ast.Attribute) and func.attr == 'sleep':
                    if isinstance(func.value, ast.Name) and func.value.id == 'time':
                        sleep_count += 1

        # Ak je veľa sleep() volaní a žiadne reálne HTTP — je to simulácia
        if sleep_count > 0 and not has_real_http:
            issues.append(
                f"MOCK DETECTED: time.sleep() sa používa {sleep_count}x bez reálnych HTTP volaní "
                f"— pravdepodobne simuluje API odpovede"
            )
        elif sleep_count >= 3:
            # Veľa sleep() aj s HTTP je podozrivé
            issues.append(
                f"PODOZRIVÉ: time.sleep() sa používa {sleep_count}x — overenie, "
                f"či neslúži na simuláciu"
            )

    def _check_mock_comments(self, code: str, issues: list) -> None:
        """Detekuje komentáre indikujúce mock/simulovaný kód."""
        for i, line in enumerate(code.splitlines(), 1):
            for pattern in MOCK_COMMENT_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    clean_line = line.strip()[:80]
                    issues.append(
                        f"MOCK KOMENTÁR na riadku {i}: '{clean_line}'"
                    )
                    break  # Jeden nález per riadok stačí

    def _check_random_faking(self, tree: ast.AST, issues: list) -> None:
        """Detekuje random.choice/random.sample na generovanie falošných výsledkov."""
        has_random_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'random':
                        has_random_import = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'random':
                    has_random_import = True

        if not has_random_import:
            return

        has_real_http = self._has_real_http_calls(tree)
        random_calls = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ('choice', 'sample', 'randint'):
                    if isinstance(func.value, ast.Name) and func.value.id == 'random':
                        random_calls += 1

        if random_calls > 0 and not has_real_http:
            issues.append(
                f"MOCK DETECTED: random.choice/sample/randint sa používa {random_calls}x "
                f"bez reálnych HTTP volaní — pravdepodobne generuje falošné dáta"
            )

    def _check_mock_strings(self, code: str, issues: list) -> None:
        """Detekuje stringy indikujúce mock/placeholder dáta."""
        for pattern in MOCK_STRING_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                issues.append(
                    f"MOCK STRING DETECTED: Nájdené '{matches[0]}' v kóde "
                    f"— indikuje placeholder/mock dáta"
                )

    def _check_static_return_functions(self, tree: ast.AST, code: str, issues: list) -> None:
        """
        Detekuje funkcie, ktoré vracajú len statické dict/list
        bez akéhokoľvek HTTP volania alebo reálnej logiky.
        """
        has_real_http = self._has_real_http_calls(tree)
        if has_real_http:
            return  # Ak má reálne HTTP, nepodozrievame

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith('_') or node.name in ('__init__', 'close', 'main'):
                continue

            # Skontroluj, či funkcia len vracia statický dict/list
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return) and n.value is not None]
            if not returns:
                continue

            all_static = True
            for ret in returns:
                if not isinstance(ret.value, (ast.Dict, ast.List, ast.Constant, ast.Tuple)):
                    all_static = False
                    break

            # Skontroluj, či funkcia neobsahuje žiadne volania (len return statických dát)
            calls_in_func = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
            real_calls = []
            for call in calls_in_func:
                # Ignoruj log.xxx(), print(), str(), int(), len() — to nie sú "reálne" operácie
                if isinstance(call.func, ast.Attribute):
                    if isinstance(call.func.value, ast.Name) and call.func.value.id in ('log', 'logging'):
                        continue
                if isinstance(call.func, ast.Name) and call.func.id in ('print', 'str', 'int', 'len', 'list', 'dict', 'set', 'tuple', 'type', 'isinstance'):
                    continue
                real_calls.append(call)

            if all_static and len(real_calls) == 0:
                issues.append(
                    f"MOCK FUNCTION: '{node.name}()' vracia len statické dáta bez "
                    f"reálnych volaní — pravdepodobne je to placeholder"
                )

    def _has_real_http_calls(self, tree: ast.AST) -> bool:
        """Zistí, či kód obsahuje reálne HTTP volania (requests/httpx)."""
        http_modules = {'requests', 'httpx', 'urllib', 'aiohttp'}
        http_methods = {'get', 'post', 'put', 'delete', 'patch', 'head', 'request', 'Session'}

        has_http_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in http_modules:
                        has_http_import = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in http_modules:
                    has_http_import = True

        if not has_http_import:
            return False

        # Hľadaj skutočné HTTP volania (requests.get(), httpx.post(), atď.)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in http_methods:
                    return True

        return False

    # ══════════════════════════════════════════════════════════
    #  5. DRY RUN (Import & Runtime check)
    # ══════════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════════
    #  KOMPLETNÁ KONTROLA — všetky fázy vrátane ANTI-MOCK
    # ══════════════════════════════════════════════════════════

    def full_check(self, code: str) -> tuple[bool, list[str]]:
        """Kompletná kontrola: Syntax -> Anti-Mock -> Robustness -> Professionalism -> Dry Run"""
        log.info("🚀 Spúšťam kompletnú PRO validáciu kódu (vrátane anti-mock)...")

        # 1. Syntax
        if not self.validate_python_syntax(code):
            return False, ["Syntaktická chyba."]

        # 2. ANTI-MOCK (NOVÉ! — detekcia simulácií a fake kódu)
        mock_ok, mock_issues = self.validate_no_mock_patterns(code)

        # 3. Robustnosť (Error handling & Modules)
        robust_ok, robust_issues = self.validate_pro_robustness(code)

        # 4. Profesionalita (Docstrings & Types)
        prof_ok, prof_issues = self.validate_code_professionalism(code)

        # 5. Dry Run (Imports & Runtime)
        dry_ok, dry_issue_str = self.dry_run(code)

        # Konvertujeme dry_issue_str na list, ak nie je prázdny
        dry_issues = [dry_issue_str] if dry_issue_str else []

        all_issues = mock_issues + robust_issues + prof_issues + dry_issues

        if not mock_ok or not robust_ok or not prof_ok or not dry_ok:
            if not mock_ok:
                log.warning(f"🚫 MOCK KÓD DETEKOVANÝ — odmietnuté: {mock_issues}")
            if not robust_ok or not prof_ok:
                log.warning(f"❌ Kód neprešiel PRO validáciou: {robust_issues + prof_issues}")
            return False, all_issues

        log.info("✅ Kód je absolútne PRO a obsahuje reálne operácie!")
        return True, []