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

### CRITICAL RULES FOR CODE:
1. DO NOT wrap Python code in markdown backticks (```). Write raw Python code directly as the string value.
2. Use ONLY these libraries: os, json, re, datetime, smtplib, sqlite3, subprocess, tempfile, logging, httpx, requests, csv, pathlib, argparse, hashlib, urllib, apscheduler
3. NEVER use flask, django, fastapi, notion_client, googlesearch, or any unlisted library.
4. Every function MUST have a docstring and type hints.
5. Code MUST include try/except error handling.
6. In JSON strings, use \\n for newlines inside code content.

### EXAMPLE OF CORRECT OUTPUT:
{{
  "metadata": {{"title": "Python Automation Kit", "slug": "python-auto-kit", "description": "Professional automation toolkit"}},
  "marketing": {{"description": "Best Python automation guide", "social_hooks": ["Automate everything!", "Save 10 hours/week"]}},
  "content_structure": [
    {{"type": "heading", "level": 1, "text": "Introduction"}},
    {{"type": "text", "text": "This guide covers practical automation techniques."}},
    {{"type": "prompt", "title": "Automation Prompt", "content": "Create a Python script that automates daily reporting."}},
    {{"type": "code", "title": "Report Generator", "language": "python", "content": "import json\\nimport logging\\n\\nlog = logging.getLogger(__name__)\\n\\ndef generate_report(data: dict) -> str:\\n    \\"\\"\\"Generate a formatted report from data.\\"\\"\\"\\n    try:\\n        return json.dumps(data, indent=2)\\n    except Exception as e:\\n        log.error(f\\"Report failed: {{e}}\\")\\n        return \\"\\"\\n"}}
  ],
  "pro_kit": {{
    "scripts": [{{"name": "report_tool.py", "content": "import json\\nimport logging\\n\\nlog = logging.getLogger(__name__)\\n\\ndef main() -> None:\\n    \\"\\"\\"Main entry point for the report tool.\\"\\"\\"\\n    try:\\n        data = {{\\"status\\": \\"ok\\"}}\\n        print(json.dumps(data))\\n    except Exception as e:\\n        log.error(f\\"Error: {{e}}\\")\\n\\nif __name__ == \\"__main__\\":\\n    main()", "description": "Standalone report generation tool"}}],
    "requirements": ["httpx"]
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