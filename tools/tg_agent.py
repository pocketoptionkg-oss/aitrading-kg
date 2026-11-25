"""AITRADING.KG — боттогу ИИ-жардамчы (конверсия).

1) Дожим: катталуу/толуктоо бүтө электерге 2 күндө 1 жолу жеке билдирүү (статуска жараша), 10:00–20:00 Бишкек,
   көп дегенде FU_MAX жолу, «🔕» менен өчүрүлөт. ANTHROPIC_API_KEY бар болсо — текстти ИИ жазат, жок болсо — шаблон.
2) Эркин суроо: колдонуучу менюдан тышкары жазса — ИИ жооп берет (трейдинг гана), анын статусун эске алып.
   Ачкыч жок болсо — None (бот мурдагыдай менюну көрсөтөт).
Чектөөлөр: киреше убада кылынбайт, 18+, тобокел эскертүү; бир колдонуучуга күнүнө AI_DAILY суроо.
"""
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

BISHKEK = timezone(timedelta(hours=6))
FU_EVERY = 48 * 3600                                  # 2 күндө 1 жолу
FU_MAX = int(os.environ.get("TG_FU_MAX", "6"))        # бир адамга эң көп дожим
AI_DAILY = int(os.environ.get("TG_AI_DAILY", "20"))
MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-5-5")
MIN_DEP = os.environ.get("TG_MIN_DEP_BINODEX", "20")


def ai_on():
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


def stage(u, free_left):
    st = u.get("status")
    if st in ("active", "blocked") or u.get("broker") == "admin":
        return None
    if st == "rejected":
        return "rereg"
    if st == "suspended":
        return "comeback"
    if st == "wait_dep":
        return "deposit"
    if st == "pending":
        return None                                    # админ текшерип жатат — тынчсыздандырбайбыз
    if not u.get("trader_id"):
        return "register" if free_left <= 0 else "try_free"
    return "register"


TPL = {
    "ru": {
        "register": ["{name}, привет! 👋 Это AI TRADING KG. Чтобы получать все сигналы (BinoDex 5/3/2 мин и фьючерсы BingX), осталось зарегистрироваться по нашей ссылке — 2 минуты. Помочь пошагово?",
                     "{name}, сигналы приходят каждый день в сессии 08:00–11:00 и 19:00 до закрытия рынка. Вы ещё не в команде — регистрация по ссылке и доступ откроется. Вопросы — просто напишите сюда."],
        "try_free": ["{name}, у вас есть бесплатные сигналы 🎁 Нажмите «⭐ Сигналы» — посмотрите, как работает анализатор, прежде чем решать.",
                     "{name}, попробуйте бесплатный сигнал в «⭐ Сигналы» — бот сам выберет лучший актив сейчас."],
        "deposit": ["{name}, регистрация есть ✅ Осталось пополнить счёт (BinoDex — от ${dep}) — и сигналы откроются автоматически. Нужна помощь с пополнением?",
                    "{name}, напоминаю: после пополнения нажмите «🔐 Проверить через BinoDex» — бот всё проверит сам, без скриншотов."],
        "rereg": ["{name}, ваш прошлый аккаунт открыт через другого партнёра. Зарегистрируйтесь заново по нашей ссылке на новую почту — и пришлите новый ID, доступ откроем."],
        "comeback": ["{name}, давно не заходили — доступ к сигналам на паузе. Нажмите «👤 Профиль» → вернуть доступ, это быстро."],
    },
    "kg": {
        "register": ["{name}, салам! 👋 Бул AI TRADING KG. Бардык сигналдарды алуу үчүн (BinoDex 5/3/2 мүн жана BingX фьючерс) биздин шилтеме менен катталуу калды — 2 мүнөт. Кадам-кадам жардам берейинби?",
                     "{name}, сигналдар күн сайын 08:00–11:00 жана 19:00дөн рынок жабылганга чейин келет. Сиз али командада эмессиз — шилтеме менен катталыңыз, доступ ачылат. Суроо болсо — ушул жерге жазыңыз."],
        "try_free": ["{name}, сизде акысыз сигналдар бар 🎁 «⭐ Сигналдар» баскычын басып, анализатордун ишин көрүңүз.",
                     "{name}, «⭐ Сигналдар» бөлүмүндө акысыз сигналды байкап көрүңүз — бот азыркы эң мыкты активди өзү тандайт."],
        "deposit": ["{name}, катталуу бар ✅ Эсепти толуктоо гана калды (BinoDex — ${dep}дан) — сигналдар өзү ачылат. Толуктоого жардам керекпи?",
                    "{name}, эскертем: толуктагандан кийин «🔐 BinoDex аркылуу текшерүү» басыңыз — бот скриншотсуз өзү текшерет."],
        "rereg": ["{name}, мурунку аккаунтуңуз башка партнёр аркылуу ачылган. Биздин шилтеме менен жаңы почтага кайра катталып, жаңы ID жөнөтүңүз — доступ ачабыз."],
        "comeback": ["{name}, көптөн бери кирген жоксуз — сигналдарга доступ тындырылган. «👤 Профиль» → доступту кайтаруу, тез эле."],
    },
}

SYSTEM = """Ты — живой и дружелюбный помощник Telegram-бота AI TRADING KG (автор — трейдер TRADER KG из Кыргызстана).
Отвечай на языке пользователя ({lang_name}), коротко (2–5 предложений), тепло, как человек, без канцелярита. Обращайся по имени.
Темы: только трейдинг, сигналы бота, регистрация и пополнение у партнёров BinoDex и BingX, риск-менеджмент, как пользоваться ботом и сайтом aitrading.kg.
На посторонние темы вежливо возвращай к трейдингу.
Правила честности: никогда не обещай доход и проценты прибыли, не говори «гарантированно»; сигнал — это вероятность.
Напоминай про риск: торговать только суммой, которую не жалко потерять, 1–2% депозита на сделку, 18+.
Цель — помочь человеку пройти следующий шаг: {goal}. В конце — один понятный призыв к действию (какую кнопку нажать).
Кнопки бота: «📝 Регистрация», «⭐ Сигналы», «👤 Профиль», «💬 Поддержка», «📱 AITRADING» (сайт в Telegram).
Не выдумывай факты о брокерах; минимальное пополнение BinoDex — ${dep}. Не проси пароли, коды и данные карт.
Данные пользователя: {ctx}"""

GOALS = {
    "register": "зарегистрироваться по нашей ссылке (BinoDex или BingX) и отправить ID",
    "try_free": "попробовать бесплатный сигнал в «⭐ Сигналы», затем зарегистрироваться",
    "deposit": "пополнить счёт и нажать «🔐 Проверить через BinoDex» или прислать скриншот",
    "rereg": "зарегистрироваться заново по нашей ссылке на новую почту и прислать новый ID",
    "comeback": "вернуться и восстановить доступ в «👤 Профиль»",
    None: "получать сигналы и торговать аккуратно",
}


def ctx_of(u, free_left):
    days = int((time.time() * 1000 - (u.get("created") or 0)) / 86400000) if u.get("created") else 0
    return json.dumps({"имя": u.get("first_name") or "", "статус": u.get("status"), "брокер": u.get("broker") or "не выбран",
                       "ID отправлен": bool(u.get("trader_id")), "бесплатных сигналов осталось": free_left,
                       "дней с нами": days}, ensure_ascii=False)


def _claude(system, messages, max_tokens=400):
    import anthropic
    client = anthropic.Anthropic(timeout=30.0, max_retries=1)
    resp = client.messages.create(model=MODEL, max_tokens=max_tokens, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def followup_text(u, stg, free_left):
    lang = u.get("lang") if u.get("lang") in ("ru", "kg") else "kg"
    name = (u.get("first_name") or "").strip() or ("друг" if lang == "ru" else "дос")
    if ai_on():
        try:
            sysm = SYSTEM.format(lang_name="русский" if lang == "ru" else "кыргызский", goal=GOALS.get(stg), dep=MIN_DEP, ctx=ctx_of(u, free_left))
            t = _claude(sysm, [{"role": "user", "content": "Напиши первое сообщение-напоминание этому человеку (он сейчас не пишет). Без приветствия «Здравствуйте, уважаемый»."}], 300)
            if t:
                return t
        except Exception as e:  # noqa: BLE001 — ИИ иштебесе шаблон
            print("! agent followup: %s" % str(e)[:120])
    return random.choice(TPL[lang][stg]).format(name=name, dep=MIN_DEP)


def reply(u, text, free_left, history=None):
    """Эркин суроого ИИ жообу. Ачкыч жок же ката — None."""
    if not ai_on() or not text or len(text) > 2000:
        return None
    lang = u.get("lang") if u.get("lang") in ("ru", "kg") else "kg"
    stg = stage(u, free_left)
    sysm = SYSTEM.format(lang_name="русский" if lang == "ru" else "кыргызский", goal=GOALS.get(stg), dep=MIN_DEP, ctx=ctx_of(u, free_left))
    msgs = list(history or [])[-6:] + [{"role": "user", "content": text}]
    try:
        return _claude(sysm, msgs, 500) or None
    except Exception as e:  # noqa: BLE001
        print("! agent reply: %s" % str(e)[:120])
        return None


def due(state, now=None):
    """state: {"n": жөнөтүлгөн саны, "t": акыркы убакыт (с), "off": 1}. Бишкек 10–20 саат аралыгында гана."""
    now = now or time.time()
    h = datetime.fromtimestamp(now, BISHKEK).hour
    if not 10 <= h < 20 or (state or {}).get("off"):
        return False
    return (state or {}).get("n", 0) < FU_MAX and now - (state or {}).get("t", 0) >= FU_EVERY
