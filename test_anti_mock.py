"""
Test: Anti-Mock Detection v ValidationAgent
Overuje, ze ValidationAgent spravne odmietne mock/simulovany kod
a povoli realny produkčny kod.
"""
import sys
sys.path.insert(0, ".")

from agents.validation_agent import ValidationAgent

v = ValidationAgent()

# ═══════════════════════════════════════════
# TEST 1: Mock kód so sleep simuláciou
# ═══════════════════════════════════════════
mock_code_sleep = (
    "import time\n"
    "import logging\n"
    "log = logging.getLogger(__name__)\n"
    "def fetch_data(url: str) -> dict:\n"
    '    """Fetch data from API."""\n'
    "    try:\n"
    "        time.sleep(2)  # simulate API call\n"
    "        return {'status': 'ok', 'data': ['mock result 1']}\n"
    "    except Exception as e:\n"
    "        log.error(f'Error: {e}')\n"
    "        return {}\n"
)
ok1, issues1 = v.validate_no_mock_patterns(mock_code_sleep)
print(f"TEST 1 (sleep + mock komentár): rejected={not ok1}")
for iss in issues1:
    print(f"  -> {iss}")
assert not ok1, "Mock sleep code should be rejected!"
print("  ✅ PASS\n")


# ═══════════════════════════════════════════
# TEST 2: Reálny kód s requests + BeautifulSoup
# ═══════════════════════════════════════════
real_code = (
    "import requests\n"
    "import logging\n"
    "from bs4 import BeautifulSoup\n"
    "log = logging.getLogger(__name__)\n"
    "def scrape(url: str) -> list:\n"
    '    """Scrape a page."""\n'
    "    try:\n"
    "        headers = {'User-Agent': 'Mozilla/5.0'}\n"
    "        resp = requests.get(url, headers=headers, timeout=10)\n"
    "        resp.raise_for_status()\n"
    "        soup = BeautifulSoup(resp.text, 'html.parser')\n"
    "        return [el.text for el in soup.select('h2')]\n"
    "    except requests.RequestException as e:\n"
    "        log.error(f'Error: {e}')\n"
    "        return []\n"
)
ok2, issues2 = v.validate_no_mock_patterns(real_code)
print(f"TEST 2 (real requests+BS4): passed={ok2}")
for iss in issues2:
    print(f"  -> {iss}")
assert ok2, f"Real code should pass! Issues: {issues2}"
print("  ✅ PASS\n")


# ═══════════════════════════════════════════
# TEST 3: Mock komentáre v kóde
# ═══════════════════════════════════════════
mock_comments = (
    "import requests\n"
    "import logging\n"
    "log = logging.getLogger(__name__)\n"
    "def get_data(url: str) -> dict:\n"
    '    """Get data."""\n'
    "    # placeholder function\n"
    "    try:\n"
    "        resp = requests.get(url, timeout=10)\n"
    "        return resp.json()\n"
    "    except Exception as e:\n"
    "        log.error(f'Error: {e}')\n"
    "        return {}\n"
)
ok3, issues3 = v.validate_no_mock_patterns(mock_comments)
print(f"TEST 3 (mock comment): rejected={not ok3}")
for iss in issues3:
    print(f"  -> {iss}")
assert not ok3, "Code with mock comments should be rejected!"
print("  ✅ PASS\n")


# ═══════════════════════════════════════════
# TEST 4: random.choice bez HTTP — faking výsledkov
# ═══════════════════════════════════════════
random_fake = (
    "import random\n"
    "import logging\n"
    "log = logging.getLogger(__name__)\n"
    "TOPICS = ['AI', 'Python', 'Automation', 'SEO']\n"
    "def generate_topics(count: int) -> list:\n"
    '    """Generate trending topics."""\n'
    "    try:\n"
    "        return random.sample(TOPICS, min(count, len(TOPICS)))\n"
    "    except Exception as e:\n"
    "        log.error(f'Error: {e}')\n"
    "        return []\n"
)
ok4, issues4 = v.validate_no_mock_patterns(random_fake)
print(f"TEST 4 (random faking): rejected={not ok4}")
for iss in issues4:
    print(f"  -> {iss}")
assert not ok4, "Random-based faking should be rejected!"
print("  ✅ PASS\n")


# ═══════════════════════════════════════════
# TEST 5: example.com placeholder URL
# ═══════════════════════════════════════════
example_url = (
    "import requests\n"
    "import logging\n"
    "log = logging.getLogger(__name__)\n"
    "def fetch(url: str = 'https://example.com/api') -> dict:\n"
    '    """Fetch from API."""\n'
    "    try:\n"
    "        resp = requests.get(url, timeout=10)\n"
    "        return resp.json()\n"
    "    except Exception as e:\n"
    "        log.error(f'Error: {e}')\n"
    "        return {}\n"
)
ok5, issues5 = v.validate_no_mock_patterns(example_url)
print(f"TEST 5 (example.com): rejected={not ok5}")
for iss in issues5:
    print(f"  -> {iss}")
assert not ok5, "example.com should be rejected!"
print("  ✅ PASS\n")


# ═══════════════════════════════════════════
# TEST 6: full_check — mock kód musí zlyhať aj cez full pipeline
# ═══════════════════════════════════════════
ok6, issues6 = v.full_check(mock_code_sleep)
print(f"TEST 6 (full_check with mock): rejected={not ok6}")
for iss in issues6:
    print(f"  -> {iss}")
assert not ok6, "full_check should reject mock code!"
print("  ✅ PASS\n")


print("=" * 50)
print("  ✅ ALL 6 ANTI-MOCK TESTS PASSED!")
print("=" * 50)
