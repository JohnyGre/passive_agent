# 🤖 PASSIVE AGENT

Plne autonómny agent pre pasívny príjem.
Generuje digitálne produkty 24/7 a automaticky ich publikuje na Gumroad.

## Rýchly štart

```bash
# 1. Naklonuj repozitár
git clone https://github.com/tvoj_repozitar/passive_agent.git
cd passive_agent

# 2. Vytvor a aktivuj virtuálne prostredie
python -m venv .venv
# Na Windows:
.venv\Scripts\activate
# Na macOS/Linux:
source .venv/bin/activate

# 3. Inštaluj závislosti
pip install -r requirements.txt

# 4. Nastav konfiguráciu
# Skopíruj .env.example na .env a vyplň svoje API kľúče a nastavenia
cp .env.example .env
# Otvor .env a doplň:
# GUMROAD_ACCESS_TOKEN="tvoj_gumroad_access_token"
# GUMROAD_EMAIL="tvoj_gumroad_email"
# GUMROAD_PASSWORD="tvoj_gumroad_password"
# TELEGRAM_BOT_TOKEN="tvoj_telegram_bot_token"
# TELEGRAM_CHAT_ID="tvoje_telegram_chat_id"
# OLLAMA_BASE_URL="http://localhost:11434"
# OLLAMA_MODEL="qwen2.5:3b" # Alebo iný model, ktorý generuje dobré JSONy

# 5. Uisti sa, že Ollama beží
# Spusti Ollama server v pozadí:
ollama serve
# Stiahni odporúčaný model (ak ho ešte nemáš):
ollama pull qwen2.5:3b

# 6. Spusti agenta
# Pre okamžité generovanie jedného produktu (pre testovanie):
python main.py --now
# Pre spustenie v plánovanom režime (podľa config.py):
python main.py
```

## Čo agent robí

| Čas | Úloha                               |
|-----|-------------------------------------|
| každé 4h | skenuje Google Trends a aktualizuje cache |
| 03:00 | generuje 10 (predvolené) nových produktov |
| 08:00 | denný report (zatiaľ neimplementované) |
| po generovaní | validuje kód, generuje DOCX/ZIP, marketing, cover a nahráva na Gumroad |

## Výstup

```
passive_agent/
└── output/
    ├── products/
    │   └── 20260615_123456_nazov_produktu/
    │       ├── data.json             ← záloha manifestu produktu
    │       ├── marketing_x.txt       ← marketingové texty
    │       ├── cover.jpg             ← vygenerovaný cover obrázok
    │       ├── v1_DIY_Basic/         ← základná verzia produktu (DOCX)
    │       │   └── nazov_produktu_Guide.docx
    │       └── v2_PRO_Automation_Kit/ ← PRO verzia produktu (DOCX + ZIP s kódmi)
    │           ├── nazov_produktu_Guide.docx
    │           └── nazov_produktu_PRO_Kit.zip
    └── logs/
        ├── agent.log                 ← hlavný log agenta
        └── published.json            ← záznamy o publikovaných produktoch na Gumroade
```

## Konfigurácia

Uprav `config.py` alebo `.env` súbor:
- `OLLAMA_MODEL` — ktorý model použiť pre generovanie obsahu (odporúča sa `qwen2.5:3b` alebo `qwen3-coder:480b-cloud` pre lepšie JSONy)
- `PRODUCTS_PER_DAY` — koľko produktov denne generovať (predvolené: 10)
- `TRENDS_GEO` — región pre Google Trends (napr. "SK", "US")
- `GUMROAD_ACCESS_TOKEN`, `GUMROAD_EMAIL`, `GUMROAD_PASSWORD` — pre automatický upload na Gumroad
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — pre Telegram notifikácie

## Modely (Ollama)

```bash
# Lokálny (offline, rýchly)
ollama pull qwen2.5:3b

# Lepší (cloud, pomalší)
# Zmeň v config.py: OLLAMA_MODEL = "deepseek-v3.1:671b-cloud"
```

## Nástroje pre správu

### Reset agenta
Ak chcete vymazať všetky vygenerované produkty, logy a cache:
```bash
python reset_agent.py
```

## Ďalšie kroky

- Implementácia denného reportu.
- Vylepšenie generovania kódu pre vyššiu kvalitu (docstrings, type hints, error handling).
- Rozšírenie typov produktov.
