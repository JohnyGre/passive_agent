"""
TREND AGENT
Skenuje viaceré zdroje trendov:
1. Google Trends (sk/global)
2. Reddit (vybrané subreddity s filtrom na nákupný záujem)
3. Fallback topics
"""

import json
import time
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
try:
    from pytrends.request import TrendReq
    PYTRENDS_OK = True
except ImportError:
    PYTRENDS_OK = False

from config import TRENDS_GEO, TRENDS_GEO_WIDE, TRENDS_TIMEFRAME, PRODUCT_TOPICS, LOGS_DIR

log = logging.getLogger("TrendAgent")

# Kľúčové slová indikujúce problém alebo potrebu (vysoká nákupná motivácia)
INTENT_KEYWORDS = {
    "problem": ["struggling with", "how to fix", "tired of", "issue with", "help with"],
    "solution": ["best tool for", "recommendation", "looking for", "alternative to"],
    "product": ["template", "prompt", "guide", "workflow", "checklist", "blueprint", "course"],
    "value": ["passive income", "automate", "save time", "make money", "scaling"]
}

class TrendAgent:
    def __init__(self):
        self.cache_file = LOGS_DIR / "trends_cache.json"
        self.pytrends   = None
        self.client     = httpx.Client(timeout=15.0, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        })
        if PYTRENDS_OK:
            try:
                self.pytrends = TrendReq(hl="sk-SK", tz=60, timeout=(10, 25))
            except Exception as e:
                log.warning(f"pytrends init failed: {e}")

    def scan(self) -> list[dict]:
        results = []

        # 1. Google Trends (Aktuálne vyhľadávania)
        if self.pytrends:
            results += self._from_google_trends()

        # 2. Reddit (Hlbšia analýza potrieb a "pain pointov")
        results += self._from_reddit()

        # 3. Záložné témy
        results += self._fallback_topics()

        # Deduplikácia a skórovanie
        seen = set()
        unique = []
        for r in results:
            key = r["keyword"].lower().strip()
            if key not in seen and len(key) > 3:
                seen.add(key)
                unique.append(r)

        # Zoradenie podľa skóre (najlepšie nápady hore)
        unique.sort(key=lambda x: x["score"], reverse=True)
        self._save_cache(unique)
        
        log.info(f"Trend scan complete: {len(unique)} potential topics analyzed")
        return unique[:15]

    def _from_google_trends(self) -> list[dict]:
        results = []
        try:
            trending = self.pytrends.trending_searches(pn="slovakia")
            for kw in trending[0].tolist()[:10]:
                results.append({"keyword": kw, "score": 90, "source": "google_trending_sk"})
        except Exception as e:
            log.warning(f"Google Trending failed: {e}")
        return results

    def _calculate_reddit_score(self, title: str, sub: str) -> int:
        """Vypočíta skóre na základe nákupnej motivácie v titulku."""
        score = 60 # Základné skóre
        title_lc = title.lower()

        # Bonus za "pain point" (ľudia hľadajú riešenie problému)
        for kw in INTENT_KEYWORDS["problem"]:
            if kw in title_lc: score += 15
            
        # Bonus za dopyt po produkte (hľadajú template, guide, atď.)
        for kw in INTENT_KEYWORDS["product"]:
            if kw in title_lc: score += 20
            
        # Bonus za hľadanie nástrojov/odporúčaní
        for kw in INTENT_KEYWORDS["solution"]:
            if kw in title_lc: score += 10

        # Subreddit váha
        if sub in ["SideHustle", "PassiveIncome"]: score += 5
        if sub == "ChatGPT": score += 2

        return min(score, 100)

    def _from_reddit(self) -> list[dict]:
        """Skenuje Reddit s dôrazom na príspevky, ktoré naznačujú nákupný záujem."""
        subs = ["SideHustle", "ChatGPT", "automation", "PassiveIncome", "solopreneur", "entrepreneur"]
        results = []
        
        for sub in subs:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                resp = self.client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for post in data.get("data", {}).get("children", []):
                        title = post["data"]["title"]
                        ups = post["data"].get("ups", 0)
                        
                        # Filtrujeme len príspevky s určitým skóre záujmu
                        r_score = self._calculate_reddit_score(title, sub)
                        
                        # Ak má príspevok aspoň jeden "nákupný" keyword alebo je veľmi populárny
                        if r_score > 70 or (ups > 100 and len(title) < 100):
                            clean_title = self._clean_reddit_title(title)
                            if clean_title:
                                results.append({
                                    "keyword": clean_title,
                                    "score": r_score,
                                    "source": f"reddit_r_{sub}"
                                })
                time.sleep(1.5) # Rešpektujeme rate limit
            except Exception as e:
                log.warning(f"Reddit scan failed for r/{sub}: {e}")
        return results

    def _clean_reddit_title(self, title: str) -> str:
        """Prevedie titulok z Redditu na tému vhodnú pre produkt."""
        # Odstráni zátvorky a meta informácie
        t = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
        # Odstráni otázniky na konci
        t = t.rstrip('?')
        # Ak je to príliš dlhé, osekni to
        if len(t) > 60:
            t = t[:57] + "..."
        if len(t) < 10: return ""
        return t

    def _fallback_topics(self) -> list[dict]:
        fallback = [
            ("AI prompt engineering for marketing", 75),
            ("Automated SEO reporting templates", 70),
            ("Python scripts for lead generation", 65),
            ("Notion operating system for freelancers", 72),
            ("Custom GPTs for business automation", 68),
        ]
        return [{"keyword": kw, "score": score, "source": "fallback"} for kw, score in fallback]

    def _save_cache(self, data: list):
        cache = {"timestamp": datetime.now().isoformat(), "trends": data}
        self.cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    def load_cache(self) -> list[dict]:
        if self.cache_file.exists():
            try:
                cache = json.loads(self.cache_file.read_text())
                return cache.get("trends", [])
            except Exception: pass
        return self._fallback_topics()
    
    def close(self):
        self.client.close()
