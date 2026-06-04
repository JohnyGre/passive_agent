"""
CONTENT AGENT - PRO VERSION
Optimalizovaný pre nízku RAM (keep_alive: 0).
"""

import json
import logging
import httpx
import re
from datetime import datetime

from config import OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("ContentAgent")

class ContentAgent:
    def __init__(self):
        self.client = httpx.Client(timeout=300.0)

    def generate(self, topic: str, product_type: str = "mini_guide") -> dict | None:
        from agents.content_agent import TEMPLATES # Predpokladáme, že šablóny sú definované
        
        prompt = TEMPLATES.get(product_type, TEMPLATES["mini_guide"]).format(topic=topic)
        log.info(f"Generujem PRO obsah pre: {topic}")

        try:
            response = self.client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": 0, # UVOĽNENIE RAM HNEĎ PO GENERÁVANÍ
                    "options": {"temperature": 0.3, "num_predict": 4096}
                }
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            
            parsed = self._parse_json(raw)
            if not parsed:
                return {"title": topic, "raw_content": raw, "_meta": {"type": product_type, "parse_failed": True}}

            parsed["_meta"] = {
                "topic": topic, "type": product_type, "model": OLLAMA_MODEL,
                "generated_at": datetime.now().isoformat()
            }
            return parsed
        except Exception as e:
            log.error(f"Content gen failed: {e}")
            return None

    def _parse_json(self, text: str) -> dict | None:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        try:
            return json.loads(clean)
        except:
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start >= 0 and end > start:
                try: return json.loads(clean[start:end])
                except: pass
        return None

    def close(self):
        self.client.close()

TEMPLATES = {
    "mini_guide": """You are an expert Python developer. Create a "Plug & Play Automation Kit" for {topic}. JSON object only.""",
    "prompt_pack": """You are a Prompt Engineer. Create a "Premium {topic} Prompt Strategy". JSON object only."""
}
