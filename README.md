# 🤖 PASSIVE AGENT

Plne autonómny agent pre pasívny príjem.
Generuje digitálne produkty 24/7 bez tvojho zásahu.

## Rýchly štart

```bash
# 1. Inštaluj závislosti
pip install apscheduler httpx pytrends requests fpdf2

# 2. Uisti sa že Ollama beží
ollama serve
# (v novom terminál)
ollama pull qwen2.5:3b

# 3. Spusti agenta
python main.py
```

## Čo agent robí

| Čas | Úloha                 |
|-----|-----------------------|
| každé 4h | skenuje Google Trends |
| 03:00 | generuje 5 produktov  |
| 08:00 | denný report          |

## Výstup

```
passive_agent/
└── output/
    ├── products/
    │   └── 20260530_030000_ai_prompt_pack/
    │       ├── ai_prompt_pack.txt    ← predajný súbor
    │       ├── ai_prompt_pack.pdf    ← (ak fpdf2 nainštalovaný)
    │       └── data.json             ← záloha
    └── logs/
        ├── agent.log
        └── stats.json
```

## Konfigurácia

Uprav `config.py`:
- `OLLAMA_MODEL` — ktorý model použiť
- `PRODUCTS_PER_DAY` — koľko produktov denne
- `TRENDS_GEO` — región pre trendy

## Modely (Ollama)

```bash
# Lokálny (offline, rýchly)
ollama pull qwen2.5:3b

# Lepší (cloud, pomalší)
# Zmeň v config.py: OLLAMA_MODEL = "deepseek-v3.1:671b-cloud"
```

## Voliteľné: PDF výstup

```bash
pip install fpdf2
```

## Voliteľné: Telegram notifikácie

1. Vytvor bota cez @BotFather
2. Doplň do `config.py`:
   ```python
   TELEGRAM_TOKEN   = "tvoj_token"
   TELEGRAM_CHAT_ID = "tvoje_id"
   ```

## Ďalší krok: Gumroad upload

Až nazbieraš produkty → postavíme Gumroad publisher agent.
