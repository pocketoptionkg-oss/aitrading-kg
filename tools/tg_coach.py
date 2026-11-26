"""YouTube-план автора жана эскертмелер (ээсине гана, Telegram аркылуу).

План (CHANGE: YT_PLAN_* чөйрө өзгөрмөлөрү):
  • Стрим — шейшемби, бейшемби, ишемби 20:00 (Бишкек), 45–60 мүн
  • Узун видео — жумасына 1 (жекшембиге чейин)
  • Shorts — күн сайын 1
Канал ачык RSS аркылуу текшерилет (ачкыч керек эмес): https://www.youtube.com/feeds/videos.xml?channel_id=…
"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BISHKEK = timezone(timedelta(hours=6))
CHANNEL = os.environ.get("YT_CHANNEL_ID", "UC06csDRexVZ85LGtLq8N2iQ")
STREAM_DAYS = [int(x) for x in os.environ.get("YT_PLAN_STREAM_DAYS", "1,3,5").split(",")]   # 0=дүйшөмбү … 1=шейшемби, 3=бейшемби, 5=ишемби
STREAM_HH = int(os.environ.get("YT_PLAN_STREAM_HOUR", "20"))
DAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
UA = "Mozilla/5.0 (aitrading.kg coach)"

TITLES = [
    "ТҮЗ ЭФИР: ИИ сигнал берет — 5 мүнөттө текшеребиз!",
    "Бүгүн рынок кайда? Түз эфирде соода + сигналдар",
    "Жаңы баштагандар үчүн: 100$ менен кантип баштайм — ТҮЗ ЭФИР",
    "Кечки сессия: ИИ vs мен — ким туура? ТҮЗ ЭФИР",
    "Догон керекпи? Түз эфирде көрсөтөм",
    "Рынок кулап жатабы? Түз эфирде анализ + соода",
    "Сигнал келди — кирем! TRADER KG түз эфир",
]
SHORT_IDEAS = [
    "Стримдеги эң мыкты кирүү — 30 секундда (экрандан сумма менен)",
    "«Эмне үчүн бул жерден кирдим?» — 1 график, 1 себеп",
    "Минус болду — эмне үйрөндүм (чынчыл)",
    "ИИ-сигнал ботто кандай келет — экрандан көрсөт",
    "Жаңы баштагандын 1 катасы — 20 секундда",
    "Бүгүнкү маанилүү жаңылык — рынокко эмне болот?",
    "Колдоо/каршылык деңгээли — 3 кадам менен",
]
VIDEO_IDEAS = [
    "Жуманын жыйынтыгы: сигналдардын ✓/✗, мыкты жана начар соода",
    "BinoDex'те 0дөн баштоо: катталуу → толуктоо → биринчи сигнал",
    "ИИ-анализатор кантип иштейт (aitrading.kg) — толук көрсөтмө",
    "Догон стратегиясы: качан болот, качан болбойт",
]


def fetch_feed():
    req = urllib.request.Request("https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        t = r.read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(r"<entry>.*?<yt:videoId>(.*?)</yt:videoId>.*?<title>(.*?)</title>.*?<link rel=\"alternate\" href=\"(.*?)\".*?<published>(.*?)</published>", t, re.S):
        vid, title, link, pub = m.groups()
        ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()
        out.append({"id": vid, "title": title, "t": ts, "short": "/shorts/" in link})
    return out


def is_live(vid, cache):
    """Видео баракчасынан: стрим болгонбу (isLiveContent). Натыйжа кэштелет."""
    if vid in cache:
        return cache[vid]
    try:
        req = urllib.request.Request("https://www.youtube.com/watch?v=" + vid, headers={"User-Agent": UA, "Accept-Language": "ru"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
        live = '"isLiveContent":true' in html
    except Exception:  # noqa: BLE001 — белгисиз болсо аталышынан
        live = None
    cache[vid] = live
    return live


def classify(items, cache):
    for x in items:
        if x["short"]:
            x["kind"] = "short"
        else:
            lv = is_live(x["id"], cache)
            if lv is None:
                lv = bool(re.search(r"эфир|ЭФИР|стрим|СТРИМ|🔴|прям", x["title"]))
            x["kind"] = "live" if lv else "video"
    return items


def week_start(now):
    d = datetime.fromtimestamp(now, BISHKEK)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def plan_text(items, now):
    ws = week_start(now)
    wk = [x for x in items if x["t"] >= ws]
    n = {k: sum(1 for x in wk if x["kind"] == k) for k in ("live", "video", "short")}
    today = datetime.fromtimestamp(now, BISHKEK).weekday()
    planned_streams = sum(1 for d in STREAM_DAYS if d <= today)
    lines = ["🎬 <b>YouTube-план</b> (неделя с %s)" % datetime.fromtimestamp(ws, BISHKEK).strftime("%d.%m"), "",
             "🔴 Стримы: <b>%d</b> из %d · дни: %s в %02d:00, 45–60 мин" % (n["live"], len(STREAM_DAYS), ", ".join(DAYS_RU[d] for d in STREAM_DAYS), STREAM_HH),
             "🎞 Видео: <b>%d</b> из 1 · до воскресенья" % n["video"],
             "📱 Shorts: <b>%d</b> из 7 · каждый день по 1" % n["short"]]
    if n["live"] < planned_streams:
        lines.append("\n⚠️ Отстаёте: по плану к сегодняшнему дню %d стрим(а), было %d." % (planned_streams, n["live"]))
    lines += ["", "<b>Правила каждого стрима:</b>",
              "1. Запланировать трансляцию в Studio за день (подписчикам придёт напоминание)",
              "2. Название на кыргызском, живое, без обещаний дохода",
              "3. Первые 2 строки описания — ссылки на бота и канал",
              "4. Анонс в канал и бот: за день и за час",
              "5. Первая сделка в первые 3 минуты, длина 45–60 мин, 1 эфир в день",
              "6. На следующий день — 2–3 Shorts из лучших моментов"]
    return "\n".join(lines)


class Coach:
    """App'ке тиркелет: app.send(owner, text), app.db.kv/kv_set."""

    def __init__(self, app):
        self.app = app
        self.items, self.t = [], 0

    def refresh(self, now):
        if now - self.t < 15 * 60:
            return self.items
        cache = self.app.db.kv("yt_live_cache") or {}
        try:
            self.items = classify(fetch_feed(), cache)
            self.t = now
            self.app.db.kv_set("yt_live_cache", {k: v for k, v in list(cache.items())[-60:]})
        except Exception as e:  # noqa: BLE001
            print("! coach feed: %s" % str(e)[:100])
        return self.items

    def once(self, key):
        """Бир күндө бир жолу гана (ачкыч боюнча)."""
        day = datetime.now(BISHKEK).strftime("%Y-%m-%d")
        k = "coach:%s:%s" % (key, day)
        if self.app.db.kv(k):
            return False
        self.app.db.kv_set(k, 1)
        return True

    def tick(self):
        owner = getattr(self.app, "owner", None)
        if not owner or self.app.db.kv("coach_off"):
            return
        now = time.time()
        d = datetime.fromtimestamp(now, BISHKEK)
        hm, wd = d.hour * 60 + d.minute, d.weekday()
        items = self.refresh(now)
        if not items:
            return
        day0 = d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = [x for x in items if x["t"] >= day0]
        i = d.toordinal()
        stream_day = wd in STREAM_DAYS
        # 1) Стрим күнү: 18:30 — даярдык
        if stream_day and hm >= STREAM_HH * 60 - 90 and hm < STREAM_HH * 60 and self.once("prep"):
            t = TITLES[i % len(TITLES)]
            self.app.send(owner, "📅 <b>Сегодня стрим в %02d:00</b>\n\n1. Запланируйте трансляцию в Studio (если ещё нет)\n"
                                 "2. Название, например:\n<code>%s</code>\n3. Анонс в канал и бот — сейчас\n"
                                 "4. Первая сделка в первые 3 минуты, 45–60 мин." % (STREAM_HH, t))
        # 2) Стрим күнү: 21:30 — болдубу?
        if stream_day and hm >= STREAM_HH * 60 + 90 and not any(x["kind"] == "live" for x in today) and self.once("missed"):
            nxt = next((DAYS_RU[(wd + k) % 7] for k in range(1, 8) if (wd + k) % 7 in STREAM_DAYS), "")
            self.app.send(owner, "⚠️ <b>Сегодня стрима не было</b> — по плану был в %02d:00.\n"
                                 "Пропуски сбивают привычку зрителей и уведомления YouTube. Следующий по плану: <b>%s %02d:00</b>." % (STREAM_HH, nxt, STREAM_HH))
        # 3) Эртеси күнү 11:00: кечээки стримден Shorts
        yday = [x for x in items if day0 - 86400 <= x["t"] < day0 and x["kind"] == "live"]
        if yday and hm >= 11 * 60 and self.once("clips"):
            self.app.send(owner, "✂️ Вчера был стрим «%s».\nСделайте из него <b>2–3 Shorts</b> по 20–40 сек: лучшая сделка, вход с объяснением, итог. "
                                 "Они приведут новых людей на следующий эфир." % yday[0]["title"][:80])
        # 4) Күн сайын 21:00: Shorts
        if hm >= 21 * 60 and not any(x["kind"] == "short" and now - x["t"] < 86400 for x in items) and self.once("short"):
            self.app.send(owner, "📱 <b>Сегодня ещё нет Shorts.</b> Идея на сегодня:\n«%s»\n20–40 сек, хук в первые 2 секунды, субтитры." % SHORT_IDEAS[i % len(SHORT_IDEAS)])
        # 5) Жекшемби 19:00: узун видео
        if wd == 6 and hm >= 19 * 60 and not any(x["kind"] == "video" and now - x["t"] < 7 * 86400 for x in items) and self.once("video"):
            self.app.send(owner, "🎞 <b>На этой неделе ещё нет длинного видео.</b> Идея:\n«%s»\n8–15 мин, в начале — что зритель получит." % VIDEO_IDEAS[(i // 7) % len(VIDEO_IDEAS)])
        # 6) Жекшемби 22:00: жуманын жыйынтыгы
        if wd == 6 and hm >= 22 * 60 and self.once("week"):
            self.app.send(owner, plan_text(items, now))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    its = classify(fetch_feed(), {})
    for x in its[:10]:
        print(x["kind"], datetime.fromtimestamp(x["t"], BISHKEK).strftime("%d.%m %H:%M"), x["title"][:60])
    print()
    print(plan_text(its, time.time()))
