"""
MARKETING AGENT
Generuje propagačné materiály pre sociálne siete.
Zamerané na Twitter (X) a budovanie povedomia o produkte.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from config import OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("MarketingAgent")

# ── Šablóny promptov pre marketing ───────────────────────────
PROMPTS = {
    "twitter_thread": """You are an expert digital marketer and copywriter. 
Create a high-converting Twitter (X) thread (5-7 tweets) to promote a new digital product.
Product Title: "{title}"
Description: "{description}"
Type: {type}

Structure:
1. Hook: Catchy opening about a problem the product solves.
2. The Solution: Introduce the product.
3. Value/Benefit 1: Specific detail.
4. Value/Benefit 2: Specific detail.
5. Social Proof/Urgency: Why now?
6. CTA: Tell them to check the link in bio.

Format your response as JSON only:
{{
  "thread": [
    "Tweet 1 text...",
    "Tweet 2 text...",
    "..."
  ],
  "hashtags": ["#ai", "#productivity", "..."]
}}"""
}

class MarketingAgent:
    def __init__(self):
        self.client = httpx.Client(timeout=60.0)

    def generate_marketing(self, product: dict) -> dict | None:
        """Vygeneruje marketingové texty pre produkt."""
        meta = product.get("metadata", {})
        marketing = product.get("marketing", {})
        title = meta.get("title") or product.get("title", "Digital Product")
        desc = marketing.get("description") or meta.get("description") or product.get("description", "")
        ptype = product.get("_meta", {}).get("type", "product")

        log.info(f"Generujem marketing pre: {title}")

        prompt = PROMPTS["twitter_thread"].format(
            title=title,
            description=desc,
            type=ptype
        )

        try:
            response = self.client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.8}
                }
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            
            # Simple JSON extraction
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                log.info(f"✅ Marketing vygenerovaný pre {title}")
                return data
            
            return None
        except Exception as e:
            log.error(f"Marketing gen failed: {e}")
            return None

    def save_marketing(self, marketing_data: dict, folder: Path):
        """Uloží marketingové texty do priečinka produktu."""
        path = folder / "marketing_x.txt"
        
        lines = ["═══ TWITTER (X) THREAD ═══\n"]
        thread = marketing_data.get("thread", [])
        for i, tweet in enumerate(thread, 1):
            lines.append(f"Tweet {i}/{len(thread)}:")
            lines.append(tweet)
            lines.append("-" * 20)
        
        hashtags = marketing_data.get("hashtags", [])
        if hashtags:
            lines.append("\nRecommended Hashtags:")
            lines.append(" ".join(hashtags))
            
        path.write_text("\n".join(lines), encoding="utf-8")
        log.info(f"Marketing uložený do: {path}")

    def close(self):
        self.client.close()
