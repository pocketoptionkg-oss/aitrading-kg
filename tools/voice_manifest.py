"""Боттун mp3 үндөрүнүн тизмесин түзүү / Собрать список mp3-фраз бота.

    python tools/voice_manifest.py

1. tools/bot_voice_phrases.csv ичиндеги ар бир фразаны (мисалы, ElevenLabs'те өз үнүңүз менен) жазып алыңыз.
2. Файлды так ошол ат менен сактаңыз: site/assets/audio/ky/trend_up.mp3, site/assets/audio/ru/trend_up.mp3 ж.б.
3. Бул скриптти иштетиңиз — site/assets/audio/voice.json жаңыланат.
Сайт mp3 бар фразаларды файлдан, калгандарын браузердин үнү менен айтат.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(os.path.dirname(HERE), "site", "assets", "audio")

out = {}
for lang in ("ky", "ru"):
    d = os.path.join(AUDIO, lang)
    out[lang] = sorted(f[:-4] for f in os.listdir(d) if f.lower().endswith(".mp3")) if os.path.isdir(d) else []
with open(os.path.join(AUDIO, "voice.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("ky:", len(out["ky"]), "| ru:", len(out["ru"]))
