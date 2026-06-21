"""
CONTENT AGENT - PRO VERSION (NUCLEAR PARSER)
Optimalizovaný pre nízku RAM (keep_alive: 0).
Zabezpečuje extrémnu odolnosť voči špinavým JSON výstupom.
"""

import json
import logging
import httpx
import re
from datetime import datetime

from config import OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("ContentAgent")

# ══════════════════════════════════════════════════════════
#  PROMPT ŠABLÓNY (S escaped zátvorkami pre .format())
# ══════════════════════════════════════════════════════════

MANIFEST_SCHEMA_INSTRUCTION = """
CRITICAL: You MUST output ONLY a valid JSON object. No text before or after. No markdown fences.
The JSON must follow this exact structure:
{{
  "metadata": {{"title": "string", "slug": "url-friendly-string", "description": "string"}},
  "marketing": {{"description": "sales copy", "social_hooks": ["hook 1", "hook 2"]}},
  "content_structure": [
    {{"type": "heading", "level": 1, "text": "string"}},
    {{"type": "text", "text": "string"}},
    {{"type": "prompt", "title": "string", "content": "string"}},
    {{"type": "code", "title": "string", "language": "python", "content": "string"}}
  ],
  "pro_kit": {{
    "scripts": [{{"name": "script_name.py", "content": "python_code", "description": "string"}}],
    "requirements": ["pkg1", "pkg2"]
  }}
}}

### CRITICAL REQUIREMENT — PRODUCTION-READY CODE ONLY:
You are writing code for a PAID, production-ready tool that real customers will download and run.
You MUST write fully functional code that performs REAL operations — no fakes, no simulations.

### ABSOLUTELY FORBIDDEN PATTERNS (your code will be REJECTED if ANY are found):
- time.sleep() to simulate/fake API calls or processing delays
- Hardcoded/mock data pretending to be API responses (e.g. return {{"status": "ok", "data": ["fake1"]}})
- Comments containing: "simulated", "mock", "placeholder", "example only", "demo", "dummy", "fake"
- Functions that return static strings/dicts/lists instead of making real HTTP requests
- Using random.choice() or random.sample() to fake scraped/generated results
- print() as the only output mechanism (use logging module + return values)
- Empty or no-op functions that pretend to do work
- Using 'example.com' or any placeholder URL instead of real, configurable targets

### MANDATORY REQUIREMENTS for scripts that involve web/API/data:
- MUST use requests.get()/requests.post() or httpx.get()/httpx.post() with REAL URLs
- MUST parse HTML with BeautifulSoup: from bs4 import BeautifulSoup; soup = BeautifulSoup(resp.text, "html.parser")
- MUST handle HTTP errors: check response.status_code, use try/except for ConnectionError, Timeout
- MUST include User-Agent header in HTTP requests
- MUST have configurable target URLs via argparse arguments or config variables (NOT hardcoded)
- MUST include requests>=2.31.0 and beautifulsoup4>=4.12.2 in the requirements list

### MANDATORY REQUIREMENTS for scripts that involve AI/LLM:
- If the script needs AI capabilities, MUST connect to a real API endpoint
- Use httpx or requests to call local Ollama (http://localhost:11434/api/generate) or OpenAI-compatible API
- The user must only need to set their API URL/key — no simulated AI responses

### GENERAL CODE QUALITY RULES:
1. Use ONLY standard Python libraries (os, json, re, datetime, smtplib, sqlite3, subprocess, tempfile, logging, csv, argparse, hashlib, urllib) or these external libraries: httpx, apscheduler, pytrends, requests, python-docx, beautifulsoup4.
2. DO NOT use flask, django, fastapi, notion_client, googlesearch, or any unlisted library.
3. Every function MUST have a docstring and type hints.
4. Code MUST include try/except error handling.
5. In JSON strings, use \\n for newlines inside code content.
6. DO NOT wrap Python code in markdown backticks (```). Write raw Python code directly as the string value.

### EXAMPLE OF CORRECT OUTPUT (note: real HTTP calls, real parsing, real error handling):
{{
  "metadata": {{"title": "Python Web Scraper Kit", "slug": "python-scraper-kit", "description": "Professional web scraping toolkit"}},
  "marketing": {{"description": "Production-ready Python scraper", "social_hooks": ["Scrape any website!", "Save hours of manual work"]}},
  "content_structure": [
    {{"type": "heading", "level": 1, "text": "Introduction"}},
    {{"type": "text", "text": "This toolkit provides real, working web scrapers."}},
    {{"type": "code", "title": "Web Scraper", "language": "python", "content": "import requests\\nimport logging\\nfrom bs4 import BeautifulSoup\\n\\nlog = logging.getLogger(__name__)\\n\\ndef scrape_page(url: str) -> list[dict]:\\n    \\\"\\\"\\\"Scrape data from a given URL using requests + BeautifulSoup.\\\"\\\"\\\"\\n    headers = {{\\\"User-Agent\\\": \\\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0\\\"}}\\n    try:\\n        resp = requests.get(url, headers=headers, timeout=15)\\n        resp.raise_for_status()\\n        soup = BeautifulSoup(resp.text, \\\"html.parser\\\")\\n        items = []\\n        for el in soup.select(\\\"h2, h3, p\\\"):\\n            items.append({{\\\"tag\\\": el.name, \\\"text\\\": el.get_text(strip=True)}})\\n        return items\\n    except requests.RequestException as e:\\n        log.error(f\\\"HTTP error: {{e}}\\\")\\n        return []\\n"}}
  ],
  "pro_kit": {{
    "scripts": [{{"name": "scraper_tool.py", "content": "import argparse\\nimport requests\\nimport logging\\nimport json\\nfrom bs4 import BeautifulSoup\\n\\nlog = logging.getLogger(__name__)\\nlogging.basicConfig(level=logging.INFO)\\n\\ndef scrape(url: str) -> list[dict]:\\n    \\\"\\\"\\\"Fetch and parse a web page, returning structured data.\\\"\\\"\\\"\\n    headers = {{\\\"User-Agent\\\": \\\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0\\\"}}\\n    try:\\n        resp = requests.get(url, headers=headers, timeout=15)\\n        resp.raise_for_status()\\n        soup = BeautifulSoup(resp.text, \\\"html.parser\\\")\\n        results = []\\n        for el in soup.select(\\\"h2, h3, p\\\"):\\n            results.append({{\\\"tag\\\": el.name, \\\"text\\\": el.get_text(strip=True)}})\\n        log.info(f\\\"Scraped {{len(results)}} elements from {{url}}\\\")\\n        return results\\n    except requests.RequestException as e:\\n        log.error(f\\\"Failed to scrape {{url}}: {{e}}\\\")\\n        return []\\n\\ndef main() -> None:\\n    \\\"\\\"\\\"CLI entry point for the scraper tool.\\\"\\\"\\\"\\n    parser = argparse.ArgumentParser(description=\\\"Web Scraper Tool\\\")\\n    parser.add_argument(\\\"--url\\\", required=True, help=\\\"Target URL to scrape\\\")\\n    parser.add_argument(\\\"--output\\\", default=\\\"results.json\\\", help=\\\"Output file path\\\")\\n    args = parser.parse_args()\\n    try:\\n        data = scrape(args.url)\\n        with open(args.output, \\\"w\\\", encoding=\\\"utf-8\\\") as f:\\n            json.dump(data, f, ensure_ascii=False, indent=2)\\n        log.info(f\\\"Results saved to {{args.output}}\\\")\\n    except Exception as e:\\n        log.error(f\\\"Error: {{e}}\\\")\\n\\nif __name__ == \\\"__main__\\\":\\n    main()", "description": "Production-ready web scraper with CLI interface"}}],
    "requirements": ["requests>=2.31.0", "beautifulsoup4>=4.12.2"]
  }}
}}
"""

TEMPLATES = {
    "mini_guide": f"""
You are a Senior Automation Engineer and Product Designer. 
Your task is to create a high-value "Plug & Play Automation Kit" for the topic: {{topic}}.

{MANIFEST_SCHEMA_INSTRUCTION}

Guidelines:
1. The 'content_structure' should provide deep, educational value.
2. The 'pro_kit' scripts must be professional, production-ready Python code.
3. The 'slug' must be lowercase with hyphens.
""",

    "prompt_pack": f"""
You are a World-Class Prompt Engineer. 
Create a "Premium Prompt Strategy Pack" for the topic: {{topic}}.

{MANIFEST_SCHEMA_INSTRUCTION}

Guidelines:
1. The 'content_structure' must contain highly detailed, engineered prompts.
2. The 'pro_kit' should include a Python script that helps users run these prompts via API.
"""
}

# ══════════════════════════════════════════════════════════
#  CONTENT AGENT CLASS
# ══════════════════════════════════════════════════════════

class ContentAgent:
    def __init__(self):
        self.client = httpx.Client(timeout=300.0)

    def generate(self, topic: str, product_type: str = "mini_guide", ollama_model_override: str | None = None) -> dict | None:
        template = TEMPLATES.get(product_type, TEMPLATES["mini_guide"])
        prompt = template.format(topic=topic)
        
        ollama_model = ollama_model_override if ollama_model_override else OLLAMA_MODEL

        log.info(f"Generujem PRO obsah pre: {topic} (Typ: {product_type}, Model: {ollama_model})")

        try:
            response = self.client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "keep_alive": 0,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 4096,  # Cloud model nemá VRAM limit — viac tokenov proti orezávaniu
                        "top_k": 40,
                        "top_p": 0.9
                    }
                }
            )
            response.raise_for_status()
            raw_response = response.json().get("response", "")

            parsed_data = self._parse_json(raw_response)

            if not parsed_data:
                # Tu je dôležitý debug - toto uvidíš v agent.log
                log.error(f"Parse zlyhal pre tému {topic}. Surový výstup: {raw_response}")
                return {"title": topic, "raw_content": raw_response, "_meta": {"type": product_type, "parse_failed": True}}

            parsed_data["_meta"] = {
                "topic": topic,
                "type": product_type,
                "model": ollama_model, # Používame skutočne použitý model
                "generated_at": datetime.now().isoformat()
            }
            return parsed_data

        except Exception as e:
            log.error(f"Content generation failed for {topic}: {e}")
            return None

    def _parse_json(self, raw: str) -> dict | None:
        """Ultra-robustná extrakcia JSONu (prevzaté z FileAgent)."""
        if not raw: return None
        try:
            return json.loads(raw)
        except Exception: pass

        clean = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
        try:
            return json.loads(clean)
        except Exception: pass

        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            candidate = clean[start:end]
            try:
                return json.loads(candidate)
            except Exception: pass
            try:
                return json.loads(candidate, strict=False)
            except Exception: pass

        if start >= 0 and end > start:
            fixed = self._fix_common_json_errors(candidate)
            try:
                return json.loads(fixed, strict=False)
            except Exception: pass

        log.warning("⚠️ JSON rescue zlyhal v ContentAgent, používam fallback.")
        return self._heuristic_fallback(raw)

    def _fix_common_json_errors(self, text: str) -> str:
        """Opraví najčastejšie chyby LLM v JSONe (trailing commas, necitované kľúče, atď.) - prevzaté z FileAgent."""
        text = re.sub(r",\s*([}\]])", r"\1", text)
        text = re.sub(r':\s*"([^"]*)\n', r': "\1",\n', text)
        text = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1 "\2":', text)
        return text.strip()

    def _heuristic_fallback(self, raw: str) -> dict:
        """Heuristický fallback pre JSON parsovanie (prevzaté z FileAgent)."""
        result = {"raw_content": raw}
        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', raw)
        if not title_match:
            title_match = re.search(r'title[:\s]+([^\n]{5,60})', raw, re.IGNORECASE)
        if title_match:
            result["title"] = title_match.group(1).strip()
        return result

    def close(self):
        self.client.close()