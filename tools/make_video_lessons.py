"""Видео-нускамалар сайт жана бот үчүн (кыска, үнсүз, кыргызча жазуулар менен).

    python tools/make_video_lessons.py "C:\\Users\\Admin\\Videos\\2026-11-22 17-15-10.mp4"
    python tools/make_video_lessons.py SRC --debug      # ар бир сценанын көзөмөл кадры (scratch)
    python tools/make_video_lessons.py SRC --only bot-id

Булак — автордун BinoDex'те катталуу экран жазуусу. Жеке маалымат (email, ID, кирүү коду) бүдөмүктөлөт,
Gmail'дин тизмеси жана аккаунттар кесилет. «bot-id» — боттун чатынын анимациясы (боттун чыныгы тексттери).
Чыгыш: site/assets/video/<ачкыч>.mp4 — 1280x720, 30 fps, H.264, үнсүз. Ачкычтар config.js → VIDEOS менен бирдей.
"""
import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "video")
W, H, FPS = 1280, 720, 30
FONT_B = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_S = r"C:\Windows\Fonts\seguisb.ttf"
FONT_E = r"C:\Windows\Fonts\seguiemj.ttf"
MINT = (92, 232, 170)
YELLOW = (255, 204, 21)
_fonts = {}


def font(path, size):
    k = (path, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size)
    return _fonts[k]


# ---------------------------------------------------------------- озвучка: сценарий (17 сап) жана сценаларга байлоо
VOICE_SCRIPT = {
    "kg": [
        ("reg_1", "Бинодекстин сайтына кирип, «Начать торговать» баскычын басыңыз."),
        ("reg_2", "Электрондук почтаңызды жазыңыз."),
        ("reg_3", "«У меня есть реферальный код» деген жерге белги коюп, кодду жазыңыз: трейдер кей-джи. Баары кичине тамга менен."),
        ("reg_4", "«Продолжить» баскычын басыңыз. «Реферальный код найден» деп чыкса — код туура кабыл алынды."),
        ("reg_5", "Почтаңызга алты сандан турган код келет. Ошол кодду жазыңыз."),
        ("reg_6", "Даяр, аккаунт ачылды! Адегенде демо-эсепте машыгып көрүңүз."),
        ("id_1", "Оң жактагы жогорку бурчтан профиль белгисин басыңыз."),
        ("id_2", "Бул жерде сиздин айди турат. Аны көчүрүп алыңыз — ботко ушул айдини жөнөтөсүз."),
        ("dep_1", "Эсепти толуктоо үчүн жашыл «Депозит» баскычын басыңыз."),
        ("dep_2", "Же профиль менюсунан «Пополнение счета» бөлүмүн тандаңыз."),
        ("dep_3", "Кичине суммадан баштаңыз. Жоготууга даяр болгон акчаны гана салыңыз."),
        ("bot_1", "Эми айдини Телеграм-ботко жөнөтөбүз. Ботто «Катталуу» баскычын басып, Бинодексти тандаңыз."),
        ("bot_2", "Андан кийин «Айди жөнөтүү» баскычын басыңыз."),
        ("bot_3", "Бинодекстеги айдиңизди жазып, жөнөтүңүз."),
        ("bot_4", "Эсепти толуктогонуңуздун скриншотун да жөнөтүңүз."),
        ("bot_5", "Бот катталууну жана толуктоону текшерет."),
        ("bot_6", "Текшерүүдөн өтсөңүз, доступ ачылат — ИИ сигналдары ушул чатка келет. Эсиңизде болсун: сигнал — бул ыктымалдык, кепилдик эмес."),
    ],
    "ru": [
        ("reg_1", "Откройте сайт Бинодекс и нажмите кнопку «Начать торговать»."),
        ("reg_2", "Введите свою электронную почту."),
        ("reg_3", "Поставьте галочку «У меня есть реферальный код» и введите код: трейдер кей-джи — всё маленькими буквами."),
        ("reg_4", "Нажмите «Продолжить». Если появилась надпись «Реферальный код найден» — код принят."),
        ("reg_5", "На почту придёт код из шести цифр. Введите его."),
        ("reg_6", "Готово, аккаунт открыт! Сначала потренируйтесь на демо-счёте."),
        ("id_1", "Нажмите на значок профиля в правом верхнем углу."),
        ("id_2", "Здесь ваш айди. Скопируйте его — именно этот айди вы отправите боту."),
        ("dep_1", "Чтобы пополнить счёт, нажмите зелёную кнопку «Депозит»."),
        ("dep_2", "Или выберите «Пополнение счета» в меню профиля."),
        ("dep_3", "Начинайте с небольшой суммы. Вносите только те деньги, которые готовы потерять."),
        ("bot_1", "Теперь отправим айди в Телеграм-бот. Нажмите в боте «Регистрация» и выберите Бинодекс."),
        ("bot_2", "Затем нажмите «Отправить айди»."),
        ("bot_3", "Напишите свой айди Бинодекс и отправьте."),
        ("bot_4", "Отправьте также скриншот пополнения счёта."),
        ("bot_5", "Бот проверит регистрацию и пополнение."),
        ("bot_6", "Если всё в порядке, доступ откроется — ИИ-сигналы будут приходить в этот чат. Помните: сигнал — это вероятность, а не гарантия."),
    ],
}
# (сап, сценалардын индекстери, кайсы сценадан кийин токтоп турат — үн узун болсо)
GROUPS = {
    "binodex-register": [("reg_1", [0, 1], 0), ("reg_2", [2], 2), ("reg_3", [3, 4, 5], 5), ("reg_4", [6, 7], 7),
                         ("reg_5", [8, 9, 10], 9), ("reg_6", [11], 11)],
    "binodex-id": [("id_1", [0, 1], 0), ("id_2", [2, 3], 3)],
    "binodex-real": [("dep_1", [0], 0), ("dep_2", [1, 2], 2), ("dep_3", [3], 3)],
}
# Орусча версия: кыргызча жазуулардын котормосу (видеодогу жазуулар жана боттун чаты)
LANG = "kg"
TR_RU = {
    "«Начать торговать» баскычын басыңыз": "Нажмите «Начать торговать»",
    "Email'иңизди жазыңыз": "Введите свой email",
    "«У меня есть реферальный код» → traderkg": "«У меня есть реферальный код» → traderkg",
    "Реферал коду: traderkg ✅": "Реферальный код: traderkg ✅",
    "«Продолжить» басыңыз": "Нажмите «Продолжить»",
    "✅ «Реферальный код найден» — код туура": "✅ «Реферальный код найден» — код принят",
    "Почтаңызга келген 6 сандуу кодду жазыңыз": "Введите 6-значный код из письма",
    "Даяр! Аккаунт ачылды. Адегенде — демо-эсеп": "Готово! Аккаунт открыт. Сначала — демо-счёт",
    "Оң жогорку бурчтагы профиль белгисин басыңыз": "Нажмите на значок профиля справа вверху",
    "Бул — сиздин ID": "Это ваш ID",
    "Бул — сиздин ID. Аны көчүрүп, ботко жөнөтөсүз": "Это ваш ID. Скопируйте его и отправьте боту",
    "Эсепти толуктоо: жашыл «Депозит» баскычы": "Пополнение: зелёная кнопка «Депозит»",
    "же профиль менюсунан «Пополнение счета»": "или в меню профиля — «Пополнение счета»",
    "Кичине сумма менен — жоготууга даяр болгон гана": "Начинайте с малой суммы, которую готовы потерять",
    # бот
    "Салам! 👋 Бул — AITRADING.KG боту.\n⭐ Сигналдар: катталып, ID жөнөткөндөн кийин ачылат.":
        "Привет! 👋 Это бот AITRADING.KG.\n⭐ Сигналы откроются после регистрации и отправки ID.",
    "📝 Катталуу": "📝 Регистрация",
    "📝 Брокерде катталуу\nКайсы брокерде соода кыласыз?": "📝 Регистрация у брокера\nГде будете торговать?",
    "📝 BinoDex'те катталуу — 5 кадам\n🔑 Реферал коду: traderkg": "📝 Регистрация на BinoDex — 5 шагов\n🔑 Реферальный код: traderkg",
    "🔗 BinoDex'те катталуу": "🔗 Регистрация на BinoDex",
    "✅ ID жөнөтүү": "✅ Отправить ID",
    "BinoDex ID'ңизди жазыңыз.": "Напишите свой ID BinoDex.",
    "📷 Толуктоонун скриншотун жөнөтүңүз.": "📷 Пришлите скриншот пополнения.",
    "⏳ Заявка жөнөтүлдү. Текшерилгенде бот өзү жазат.": "⏳ Заявка отправлена. После проверки бот напишет сам.",
    "✅ Доступ ачылды!\n⭐ Сигналдар ушул чатка келет.": "✅ Доступ открыт!\n⭐ Сигналы будут приходить в этот чат.",
    "«📝 Катталуу» → BinoDex": "«📝 Регистрация» → BinoDex",
    "«✅ ID жөнөтүү» басыңыз": "Нажмите «✅ Отправить ID»",
    "BinoDex ID'ңизди жазыңыз\n(мисалы: 1234567)": "Напишите свой ID BinoDex\n(например: 1234567)",
    "Толуктоонун скриншоту": "Скриншот пополнения",
    "Бот текшерет: катталуу (traderkg)\nжана толуктоо": "Бот проверит регистрацию (traderkg)\nи пополнение",
    "✅ Доступ ачылды — ⭐ сигналдар\nTelegram'га келет": "✅ Доступ открыт — ⭐ сигналы\nприходят в Telegram",
    "⭐ Сигналдар": "⭐ Сигналы", "📚 Окуу": "📚 Обучение", "💬 Колдоо": "💬 Поддержка",
    "ID'ни Telegram-ботко жөнөтүү": "Отправка ID в Telegram-бот",
    "Бот катталууну жана толуктоону текшерет": "Бот проверяет регистрацию и пополнение",
    "AITRADING.KG · Сигнал — ыктымалдык, кепилдик эмес · 18+": "AITRADING.KG · Сигнал — вероятность, а не гарантия · 18+",
    "Билдирүү…": "Сообщение…",
}


def tr(s):
    return TR_RU.get(s, s) if LANG == "ru" and isinstance(s, str) else s


BOT_SCENES = [("bot_1", 0.0, 4.9), ("bot_2", 4.9, 6.3), ("bot_3", 6.3, 8.6), ("bot_4", 8.6, 10.5), ("bot_5", 10.5, 12.2), ("bot_6", 12.2, 15.0)]
LEAD, TAIL = 0.25, 0.5          # үн сценанын башынан 0,25 с кийин башталат; аягында 0,5 с тыныгуу


def load_voice(path):
    """voice_split.py'нын JSON'у → {key: (start, end)}, 44.1 кГц моно үн."""
    import json
    import wave
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    with wave.open(os.path.join(os.path.dirname(path), meta["wav"]), "rb") as wf:
        sr = wf.getframerate()
        a = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return {l["key"]: (l["start"], l["end"]) for l in meta["lines"]}, a, sr


def fit_voice(shots, groups, vl):
    """Ар бир саптын үнүнө жараша сценаны узартуу (токтотулган кадр кошулат). → (жаңы сценалар, [(key, убакыт)])"""
    out, places, t = [], [], 0.0
    for key, idx, hold in groups:
        D = sum(shots[i].dur for i in idx)
        s, e = vl[key]
        extra = max(0.0, LEAD + (e - s) + TAIL - D)
        places.append((key, t + LEAD))
        for i in idx:
            out.append(shots[i])
            if i == hold and extra > 0.04:
                sh = shots[i]
                out.append(Shot(extra, sh.t1, None, sh.crop1, sh.crop1, sh.cap, sh.step, hl=sh.hl))
        t += D + extra
    return out, places, t


def bot_warp(vl):
    """bot-id: сценалар үнгө жараша жайлайт (≤2,2 эсе), андан ашса — акыркы абалда токтоп турат."""
    plan, places, t = [], [], 0.0
    for key, s0, s1 in BOT_SCENES:
        D = s1 - s0
        vs, ve = vl[key]
        D2 = max(D, LEAD + (ve - vs) + TAIL)
        plan.append((t, D2, s0, D, min(D2 / D, 2.2)))
        places.append((key, t + LEAD))
        t += D2

    def f(tn):
        for n0, D2, s0, D, k in plan:
            if tn < n0 + D2 or (n0, D2) == plan[-1][:2]:
                loc = tn - n0
                return s0 + min(loc / k, D)
        return BOT_SCENES[-1][2]
    return f, places, t


def voice_track(places, vl, audio, sr, total, out_wav):
    import wave
    buf = np.zeros(int((total + 0.5) * sr), dtype=np.float32)
    fade = int(0.015 * sr)
    for key, at in places:
        s, e = vl[key]
        clip = audio[int(s * sr):int(e * sr)].copy()
        if len(clip) > 2 * fade:
            clip[:fade] *= np.linspace(0, 1, fade)
            clip[-fade:] *= np.linspace(1, 0, fade)
        i = int(at * sr)
        buf[i:i + len(clip)] += clip[:max(0, len(buf) - i)]
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())


def ffmpeg_out(out_path, audio_wav=None, crf="26"):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
    if audio_wav:
        cmd += ["-i", audio_wav, "-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", out_path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


# ---------------------------------------------------------------- текст + эмодзи
def is_emoji(ch):
    cp = ord(ch)
    return cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or cp in (0x2B50, 0x231B, 0x23F3, 0x2B06, 0x2B07, 0x21AA)


def runs(text):
    out, cur, emo = [], "", None
    for ch in text:
        if ord(ch) == 0xFE0F:
            continue
        e = is_emoji(ch)
        if emo is None or e == emo:
            cur += ch
        else:
            out.append((emo, cur))
            cur = ch
        emo = e
    if cur:
        out.append((emo, cur))
    return out


def rich_len(text, size, bold=True):
    f, fe = font(FONT_B if bold else FONT_S, size), font(FONT_E, size)
    return sum((fe if e else f).getlength(s) for e, s in runs(text))


def rich_draw(d, xy, text, size, fill, bold=True):
    x, y = xy
    f, fe = font(FONT_B if bold else FONT_S, size), font(FONT_E, size)
    for e, s in runs(text):
        if e:
            if len(fill) < 4 or fill[3] > 200:               # түстүү эмодзи тунук болбойт — көбүкчө толук чыкканда гана
                d.text((x, y + size * 0.04), s, font=fe, embedded_color=True)
            x += fe.getlength(s)
        else:
            d.text((x, y), s, font=f, fill=fill)
            x += f.getlength(s)
    return x


def wrap(text, size, maxw, bold=False):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w_ in words:
            t = (cur + " " + w_).strip()
            if rich_len(t, size, bold) <= maxw or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w_
        lines.append(cur)
    return lines


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- видео окугуч
class Reader:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            sys.exit("Видео ачылган жок: " + path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 60
        self.idx, self.frame = -1, None

    def at(self, t):
        i = int(round(t * self.fps))
        if i == self.idx:
            return self.frame
        if i < self.idx or i > self.idx + 120:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            self.idx = i - 1
        while self.idx < i:
            ok, f = self.cap.read()
            if not ok:
                break
            self.idx += 1
            self.frame = f
        return self.frame


# Жеке маалымат: (t0, t1, (x0, y0, x1, y1)) — булак видеонун координаттары (1920x1080)
BLURS = [
    (8.9, 15.62, (786, 410, 1138, 474)),        # email талаасы (жазып жатканда)
    (15.62, 21.25, (786, 380, 1138, 444)),      # email талаасы (реферал талаасы ачылгандан кийин)
    (21.2, 21.6, (786, 362, 1138, 446)),        # email талаасы («Реферальный код найден»)
    (21.55, 22.45, (786, 362, 1138, 552)),      # кийинки терезеге өтүү (email кайсы жерде болсо да)
    (22.2, 24.8, (922, 510, 1100, 544)),        # «Мы отправили код на …»
    (41.8, 43.8, (955, 530, 1236, 630)),        # Gmail: кирүү коду
    (46.2, 48.3, (922, 510, 1100, 544)),
    (46.75, 48.3, (782, 552, 1140, 630)),       # киргизилген код
    (56.2, 57.35, (1436, 112, 1690, 244)),      # профиль ачылып жатканда
    (57.3, 61.0, (1546, 148, 1594, 177)),       # ID сандары («ID» жазуусу көрүнүп калат)
    (57.3, 61.0, (1562, 174, 1618, 201)),       # Binodex-сандар
    (57.3, 61.0, (1484, 198, 1632, 228)),       # email
]


def apply_blurs(img, t):
    for t0, t1, (x0, y0, x1, y1) in BLURS:
        if t0 <= t <= t1:
            roi = img[y0:y1, x0:x1]
            if roi.size == 0:
                continue
            h, w = roi.shape[:2]
            small = cv2.resize(roi, (max(1, w // 14), max(1, h // 14)), interpolation=cv2.INTER_AREA)
            roi[:] = cv2.GaussianBlur(cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST), (0, 0), 6)
    return img


# ---------------------------------------------------------------- сценалар
class Shot:
    def __init__(self, dur, t0, t1=None, crop0=(0, 0, 1920, 1080), crop1=None, cap=None, step=None,
                 hl=(), clicks=()):
        self.dur, self.t0, self.t1 = dur, t0, (t0 if t1 is None else t1)
        self.crop0, self.crop1 = crop0, (crop1 or crop0)
        self.cap, self.step, self.hl, self.clicks = cap, step, list(hl), list(clicks)


def crop_at(s, u):
    k = smooth(u)
    return tuple(a + (b - a) * k for a, b in zip(s.crop0, s.crop1))


def to_out(box, cr):
    x, y, w, h = cr
    sx, sy = W / w, H / h
    return ((box[0] - x) * sx, (box[1] - y) * sy, (box[2] - x) * sx, (box[3] - y) * sy)


def caption(img, text, step, alpha):
    text = tr(text)
    if not text or alpha <= 0:
        return img
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    size = 30
    tw = rich_len(text, size)
    chip = 46 if step else 0
    bw = tw + 44 + (chip + 14 if step else 0)
    bx, by, bh = (W - bw) / 2, H - 96, 64
    a = int(215 * alpha)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=20, fill=(9, 14, 24, a), outline=(92, 232, 170, int(90 * alpha)), width=2)
    x = bx + 22
    if step:
        d.ellipse([x, by + 9, x + chip, by + 9 + chip], fill=MINT + (int(255 * alpha),))
        sf = font(FONT_B, 24)
        sw = sf.getlength(str(step))
        d.text((x + (chip - sw) / 2, by + 15), str(step), font=sf, fill=(4, 23, 15, int(255 * alpha)))
        x += chip + 14
    tmp = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rich_draw(ImageDraw.Draw(tmp), (x, by + 13), text, size, (255, 255, 255, 255))
    if alpha < 1:
        tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * alpha)))
    ov = Image.alpha_composite(ov, tmp)
    return Image.alpha_composite(img, ov)


def render_video(reader, shots, out_path, debug_dir=None, audio_wav=None):
    total = sum(s.dur for s in shots)
    proc = None if debug_dir else ffmpeg_out(out_path, audio_wav, "26")
    n = int(round(total * FPS))
    starts, acc = [], 0.0
    for s in shots:
        starts.append(acc)
        acc += s.dur
    prev_cap = None
    for k in range(n):
        T = k / FPS
        si = max(i for i, st in enumerate(starts) if st <= T + 1e-9)
        s = shots[si]
        u = (T - starts[si]) / s.dur
        t = s.t0 + (s.t1 - s.t0) * u
        src = reader.at(t)
        if src is None:
            continue
        src = apply_blurs(src.copy(), t)
        cr = crop_at(s, u)
        x, y, w, h = cr
        M = np.float32([[W / w, 0, -x * W / w], [0, H / h, -y * H / h]])
        interp = cv2.INTER_AREA if w > W * 1.05 and s.crop0 == s.crop1 else cv2.INTER_LINEAR
        if interp == cv2.INTER_AREA:
            fr = cv2.resize(src[int(y):int(y + h), int(x):int(x + w)], (W, H), interpolation=cv2.INTER_AREA)
        else:
            fr = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        img = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).convert("RGBA")
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        # Белгилөө (кадр ичинде)
        for item in s.hl:
            box = item[0]
            col = item[1] if len(item) > 1 else MINT
            x0, y0, x1, y1 = to_out(box, cr)
            pulse = 0.55 + 0.45 * math.sin(T * 6.0)
            pad = 8
            for wdt, al in ((14, int(50 * pulse)), (4, 255)):
                d.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], radius=12, outline=col + (al,), width=wdt)
        # Басуу толкуну
        for ct, cx, cy in s.clicks:
            p = (t - ct) / 0.55 if s.t1 != s.t0 else -1
            if 0 <= p <= 1:
                ox, oy = to_out((cx, cy, cx, cy), cr)[:2]
                r = 12 + 46 * p
                d.ellipse([ox - r, oy - r, ox + r, oy + r], outline=MINT + (int(255 * (1 - p)),), width=5)
                d.ellipse([ox - 9, oy - 9, ox + 9, oy + 9], fill=MINT + (int(200 * (1 - p)),))
        img = Image.alpha_composite(img, ov)
        fade = 1.0 if s.cap == prev_cap and si > 0 else min(1.0, (T - starts[si]) / 0.25)
        img = caption(img, s.cap, s.step, fade)
        if k + 1 < n and (k + 1) / FPS >= starts[si] + s.dur - 1e-9:
            prev_cap = s.cap
        if debug_dir:
            if abs(T - (starts[si] + s.dur * 0.6)) < 0.5 / FPS:
                img.convert("RGB").save(os.path.join(debug_dir, "%s_%02d.jpg" % (os.path.basename(out_path)[:-4], si)), quality=85)
        else:
            proc.stdin.write(img.convert("RGB").tobytes())
    if proc:
        proc.stdin.close()
        proc.wait()
    return total


# ---------------------------------------------------------------- BinoDex кадрлары
FULL = (0, 0, 1920, 1080)
LAND_Z = (560, 200, 800, 450)
MODAL = (560, 250, 800, 450)
REFZ = (690, 360, 540, 304)
MAIL = (752, 287, 680, 383)
TR = (1180, 0, 740, 416)
DROP = (1400, 80, 520, 292)

REF_FIELD = (793, 482, 1131, 531)
FOUND = (783, 524, 945, 548)
ID_LINE = (1524, 148, 1612, 177)
DEMO = (1322, 6, 1450, 56)
DEPOSIT = (1480, 12, 1604, 56)
REFILL = (1688, 164, 1894, 196)


def shots_register():
    c1 = "«Начать торговать» баскычын басыңыз"
    c3 = "«У меня есть реферальный код» → traderkg"
    c4 = "Почтаңызга келген 6 сандуу кодду жазыңыз"
    return [
        Shot(1.5, 3.95, 5.15, FULL, LAND_Z, c1, 1),
        Shot(0.8, 5.15, 5.6, LAND_Z, MODAL, c1, 1, clicks=[(5.25, 973, 374)]),
        Shot(2.0, 9.0, 15.2, MODAL, MODAL, "Email'иңизди жазыңыз", 2),
        Shot(1.3, 15.2, 16.2, MODAL, REFZ, c3, 3, clicks=[(15.5, 817, 490)]),
        Shot(2.2, 16.2, 20.6, REFZ, REFZ, c3, 3, hl=[(REF_FIELD,)]),
        Shot(1.1, 20.6, None, REFZ, REFZ, "Реферал коду: traderkg ✅", 3, hl=[(REF_FIELD,)]),
        Shot(1.1, 20.6, 21.5, REFZ, MODAL, "«Продолжить» басыңыз", 4, clicks=[(21.2, 982, 628)]),
        Shot(1.5, 21.5, None, MODAL, MODAL, "✅ «Реферальный код найден» — код туура", 4, hl=[(FOUND,)]),
        Shot(1.3, 22.4, 23.5, MODAL, MODAL, c4, 5),
        Shot(1.6, 42.0, 42.9, MAIL, MAIL, c4, 5),
        Shot(1.3, 46.5, 48.05, MODAL, MODAL, c4, 5),
        Shot(2.6, 53.2, 55.0, FULL, FULL, "Даяр! Аккаунт ачылды. Адегенде — демо-эсеп", 6, hl=[(DEMO,)]),
    ]


def shots_id():
    return [
        Shot(1.1, 54.6, 55.7, FULL, TR, "Оң жогорку бурчтагы профиль белгисин басыңыз", 1),
        Shot(1.5, 55.7, 57.6, TR, TR, "Оң жогорку бурчтагы профиль белгисин басыңыз", 1, clicks=[(56.1, 1880, 36)]),
        Shot(0.8, 57.6, None, TR, DROP, "Бул — сиздин ID", 2, hl=[(ID_LINE,)]),
        Shot(2.8, 57.6, None, DROP, DROP, "Бул — сиздин ID. Аны көчүрүп, ботко жөнөтөсүз", 2, hl=[(ID_LINE,)]),
    ]


def shots_real():
    return [
        Shot(2.4, 57.6, None, TR, TR, "Эсепти толуктоо: жашыл «Депозит» баскычы", 1, hl=[(DEPOSIT,)]),
        Shot(0.8, 57.6, None, TR, DROP, "же профиль менюсунан «Пополнение счета»", 2, hl=[(REFILL,)]),
        Shot(2.2, 57.6, None, DROP, DROP, "же профиль менюсунан «Пополнение счета»", 2, hl=[(REFILL,)]),
        Shot(2.4, 57.6, None, DROP, DROP, "Кичине сумма менен — жоготууга даяр болгон гана", 3),
    ]


# ---------------------------------------------------------------- bot-id: боттун чатынын анимациясы
BG = (11, 17, 28)
CHAT_BG = (14, 22, 33)
BOT_BUBBLE = (24, 37, 51)
ME_BUBBLE = (43, 82, 120)
PH = (90, 18, 400, 684)          # телефон: x, y, w, h


def bot_timeline():
    """(t, тип, маалымат). Тексттер — tg_bot.py'дагыдай (кыскартылган)."""
    return [
        (0.0, "bot", ("Салам! 👋 Бул — AITRADING.KG боту.\n⭐ Сигналдар: катталып, ID жөнөткөндөн кийин ачылат.", [])),
        (0.0, "kbd", True),
        (1.3, "tap", ("kbd", 1)),
        (1.5, "me", "📝 Катталуу"),
        (2.1, "bot", ("📝 Брокерде катталуу\nКайсы брокерде соода кыласыз?", [["BingX", "BinoDex"]])),
        (3.3, "tap", ("inline", 1)),
        (3.8, "bot", ("📝 BinoDex'те катталуу — 5 кадам\n🔑 Реферал коду: traderkg", [["🔗 BinoDex'те катталуу"], ["✅ ID жөнөтүү"]])),
        (5.4, "tap", ("inline", 1)),
        (5.9, "bot", ("BinoDex ID'ңизди жазыңыз.", [])),
        (6.5, "type", "1234567"),
        (8.1, "send", None),
        (8.2, "me", "1234567"),
        (8.9, "bot", ("📷 Толуктоонун скриншотун жөнөтүңүз.", [])),
        (10.0, "img", None),
        (10.8, "bot", ("⏳ Заявка жөнөтүлдү. Текшерилгенде бот өзү жазат.", [])),
        (12.4, "bot", ("✅ Доступ ачылды!\n⭐ Сигналдар ушул чатка келет.", [])),
    ]


STEPS_R = [
    (1.2, "«📝 Катталуу» → BinoDex"),
    (5.0, "«✅ ID жөнөтүү» басыңыз"),
    (6.4, "BinoDex ID'ңизди жазыңыз\n(мисалы: 1234567)"),
    (8.8, "Толуктоонун скриншоту"),
    (10.7, "Бот текшерет: катталуу (traderkg)\nжана толуктоо"),
    (12.3, "✅ Доступ ачылды — ⭐ сигналдар\nTelegram'га келет"),
]
KBD = [["⭐ Сигналдар", "📝 Катталуу"], ["📚 Окуу", "👤 Профиль"], ["🌐 Сайт", "💬 Колдоо"]]


def bubble_layout(kind, data, maxw):
    """Көбүкчөнүн өлчөмү: (w, h, lines, buttons)."""
    if kind == "img":
        return 230, 150, [], []
    text, buttons = (data if kind == "bot" else (data, []))
    text, buttons = tr(text), [[tr(b) for b in row] for row in buttons]
    lines = wrap(text, 19, maxw - 28)
    h = 16 + len(lines) * 27 + 10
    bh = len(buttons) * 40
    w = max([rich_len(l, 19, False) for l in lines] + [0]) + 28
    if buttons:
        w = maxw
    return min(maxw, w), h + bh, lines, buttons


def render_bot(out_path, debug_dir=None, warp=None, total=15.0, audio_wav=None):
    tl = bot_timeline()
    px, py, pw, ph = PH
    head_h, input_h, kbd_h = 64, 52, 3 * 46 + 14
    proc = None if debug_dir else ffmpeg_out(out_path, audio_wav, "24")
    n = int(total * FPS)
    for k in range(n):
        T = warp(k / FPS) if warp else k / FPS
        img = Image.new("RGBA", (W, H), BG + (255,))
        d = ImageDraw.Draw(img)
        # фон: жумшак жашыл жарык
        for r in range(6):
            d.ellipse([820 - 300 + r * 30, 120 + r * 20, 1260 - r * 30, 620 - r * 20], fill=(14 + r * 2, 30 + r * 4, 34 + r * 3, 255))
        # телефон
        d.rounded_rectangle([px - 10, py - 10, px + pw + 10, py + ph + 10], radius=46, fill=(5, 8, 12, 255), outline=(60, 70, 85, 255), width=2)
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=38, fill=CHAT_BG + (255,))
        # баш тилке
        d.rounded_rectangle([px, py, px + pw, py + head_h + 20], radius=38, fill=(23, 33, 43, 255))
        d.rectangle([px, py + 30, px + pw, py + head_h], fill=(23, 33, 43, 255))
        d.ellipse([px + 18, py + 14, px + 56, py + 52], fill=MINT + (255,))
        d.text((px + 25, py + 22), "AI", font=font(FONT_B, 17), fill=(4, 23, 15))
        d.text((px + 68, py + 14), "AITRADING.KG бот", font=font(FONT_B, 18), fill=(240, 244, 250))
        d.text((px + 68, py + 37), "бот", font=font(FONT_S, 14), fill=(120, 150, 175))
        # абал
        show_kbd = any(kind == "kbd" and t <= T for t, kind, _ in tl)
        typed = ""
        for t, kind, data in tl:
            if kind == "type" and t <= T:
                typed = data[: max(0, min(len(data), int((T - t) / 0.18) + 1))]
            if kind == "send" and t <= T:
                typed = ""
        msgs = [(t, kind, data) for t, kind, data in tl if kind in ("bot", "me", "img") and t <= T]
        # билдирүүлөр — ылдыйдан өйдө
        area_top = py + head_h + 6
        area_bot = py + ph - input_h - (kbd_h if show_kbd else 0) - 8
        maxw = pw - 70
        y = area_bot
        drawn = []
        for t, kind, data in reversed(msgs):
            bw, bh, lines, buttons = bubble_layout(kind, data, maxw)
            y -= bh + 10
            drawn.append((t, kind, data, bw, bh, lines, buttons, y))
            if y < area_top - 400:
                break
        chat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chat)
        for t, kind, data, bw, bh, lines, buttons, y0 in drawn:
            age = T - t
            a = smooth(age / 0.25)
            off = (1 - a) * 18
            mine = kind in ("me", "img")
            x0 = px + pw - 14 - bw if mine else px + 14
            yy = y0 + off
            if yy + bh < area_top:
                continue
            col = ME_BUBBLE if mine else BOT_BUBBLE
            text_h = bh - len(buttons) * 40
            cd.rounded_rectangle([x0, yy, x0 + bw, yy + text_h], radius=16, fill=col + (int(255 * a),))
            if kind == "img":
                cd.rounded_rectangle([x0 + 6, yy + 6, x0 + bw - 6, yy + bh - 6], radius=12, fill=(18, 28, 40, int(255 * a)))
                cd.text((x0 + 22, yy + 22), "BinoDex · Пополнение", font=font(FONT_S, 15), fill=(160, 180, 200, int(255 * a)))
                cd.text((x0 + 22, yy + 52), "+ $50.00", font=font(FONT_B, 30), fill=MINT + (int(255 * a),))
                cd.line([(x0 + 22, yy + 108), (x0 + 27, yy + 113), (x0 + 35, yy + 103)], fill=MINT + (int(255 * a),), width=3)
                cd.text((x0 + 42, yy + 98), "Успешно", font=font(FONT_S, 16), fill=MINT + (int(255 * a),))
                continue
            for i, line in enumerate(lines):
                rich_draw(cd, (x0 + 14, yy + 10 + i * 27), line, 19, (235, 241, 248, int(255 * a)), bold=(i == 0 and kind == "bot" and len(lines) > 1))
            by = yy + text_h + 4
            for r, row in enumerate(buttons):
                bwid = (bw - 4 * (len(row) - 1)) / len(row)
                for c, label in enumerate(row):
                    bx = x0 + c * (bwid + 4)
                    cd.rounded_rectangle([bx, by, bx + bwid, by + 34], radius=10, fill=(33, 50, 68, int(255 * a)))
                    lw = rich_len(label, 16)
                    rich_draw(cd, (bx + (bwid - lw) / 2, by + 6), label, 16, (220, 235, 250, int(255 * a)))
                    for tt, kk, dd in tl:
                        if kk == "tap" and dd[0] == "inline" and t < tt and abs(tt - T) < 0.6:
                            # кайсы баскыч басылат: акыркы inline'дын dd[1]-орду (саптар боюнча тегиз)
                            flat = [b for rr in buttons for b in rr]
                            if dd[1] < len(flat) and flat[dd[1]] == label and drawn[0][0] == t:
                                p = (T - tt) / 0.6
                                if p >= 0:
                                    rr_ = 10 + 40 * p
                                    cxp, cyp = bx + bwid / 2, by + 17
                                    cd.ellipse([cxp - rr_, cyp - rr_, cxp + rr_, cyp + rr_], outline=MINT + (int(255 * (1 - p)),), width=4)
                by += 40
        # чат аймагын кесүү
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rectangle([px, area_top, px + pw, area_bot + 4], fill=255)
        img.paste(chat, (0, 0), Image.composite(chat, Image.new("RGBA", (W, H)), mask).getchannel("A"))
        # клавиатура (меню)
        iy = py + ph - input_h - (kbd_h if show_kbd else 0)
        d.rectangle([px, iy, px + pw, iy + input_h], fill=(23, 33, 43, 255))
        d.text((px + 20, iy + 15), typed + ("|" if typed and int(T * 3) % 2 == 0 else "") if typed else tr("Билдирүү…"),
               font=font(FONT_S, 17), fill=(235, 241, 248) if typed else (110, 130, 150))
        d.ellipse([px + pw - 46, iy + 10, px + pw - 14, iy + 42], fill=MINT + (255,) if typed else (40, 56, 72, 255))
        sx, sy = px + pw - 30, iy + 26                       # «жөнөтүү» жебеси
        d.polygon([(sx - 7, sy - 8), (sx + 9, sy), (sx - 7, sy + 8), (sx - 3, sy)], fill=(4, 23, 15) if typed else (150, 170, 190))
        if show_kbd:
            ky = iy + input_h
            d.rectangle([px, ky, px + pw, py + ph - 26], fill=(19, 28, 38, 255))
            d.rounded_rectangle([px, py + ph - 60, px + pw, py + ph], radius=38, fill=(19, 28, 38, 255))
            for r, row in enumerate(KBD):
                bwid = (pw - 24 - 6) / 2
                for c, label in enumerate(row):
                    label = tr(label)
                    bx, by = px + 12 + c * (bwid + 6), ky + 8 + r * 46
                    d.rounded_rectangle([bx, by, bx + bwid, by + 40], radius=10, fill=(36, 52, 68, 255))
                    lw = rich_len(label, 16)
                    rich_draw(d, (bx + (bwid - lw) / 2, by + 9), label, 16, (225, 235, 245))
                    for tt, kk, dd in tl:
                        if kk == "tap" and dd[0] == "kbd" and r * 2 + c == dd[1]:
                            p = (T - tt) / 0.6
                            if 0 <= p <= 1:
                                rr_ = 10 + 40 * p
                                cxp, cyp = bx + bwid / 2, by + 20
                                d.ellipse([cxp - rr_, cyp - rr_, cxp + rr_, cyp + rr_], outline=MINT + (int(255 * (1 - p)),), width=4)
        # оң жак: кадамдар
        rx, ry = 600, 92
        d.text((rx, ry - 66), tr("ID'ни Telegram-ботко жөнөтүү"), font=font(FONT_B, 34), fill=(245, 248, 252))
        d.text((rx, ry - 22), tr("Бот катталууну жана толуктоону текшерет"), font=font(FONT_S, 19), fill=(150, 165, 185))
        cy = ry + 40
        for i, (ts, txt) in enumerate(STEPS_R):
            txt = tr(txt)
            active = T >= ts and (i + 1 == len(STEPS_R) or T < STEPS_R[i + 1][0])
            done = T >= ts and not active
            col = (245, 248, 252) if active else ((150, 200, 175) if done else (90, 105, 125))
            d.ellipse([rx, cy, rx + 40, cy + 40], fill=MINT + (255,) if (active or done) else (35, 48, 64, 255))
            if done:                                          # белги — сызык менен (шрифтте «✓» жок)
                d.line([(rx + 11, cy + 21), (rx + 18, cy + 28), (rx + 30, cy + 13)], fill=(4, 23, 15), width=4, joint="curve")
            else:
                sym, sf = str(i + 1), font(FONT_B, 20)
                d.text((rx + (40 - sf.getlength(sym)) / 2, cy + 7), sym, font=sf, fill=(4, 23, 15) if active else (130, 145, 165))
            lines = txt.split("\n")
            for j, line in enumerate(lines):
                rich_draw(d, (rx + 58, cy + 6 + j * 30), line, 24 if j == 0 else 19, col, bold=(j == 0))
            cy += 40 + 30 * len(lines) + 8
        d.text((rx, H - 54), tr("AITRADING.KG · Сигнал — ыктымалдык, кепилдик эмес · 18+"), font=font(FONT_S, 16), fill=(110, 125, 145))
        if debug_dir:
            if k in (int(2.5 * FPS), int(7.5 * FPS), int(13.5 * FPS)):
                img.convert("RGB").save(os.path.join(debug_dir, "bot_%04d.jpg" % k), quality=85)
        else:
            proc.stdin.write(img.convert("RGB").tobytes())
    if proc:
        proc.stdin.close()
        proc.wait()
    return total


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="BinoDex'те катталуунун экран жазуусу (mp4)")
    ap.add_argument("--debug", help="көзөмөл кадрлар үчүн папка")
    ap.add_argument("--only", help="binodex-register,binodex-id,binodex-real,bot-id")
    ap.add_argument("--voice", help="voice_split.py'нын JSON'у, мисалы tools/voice/voice_kg.json — үн менен чыгарат")
    a = ap.parse_args()
    os.makedirs(a.debug or OUT, exist_ok=True)
    want = set((a.only or "binodex-register,binodex-id,binodex-real,bot-id").split(","))
    jobs = [("binodex-register", shots_register), ("binodex-id", shots_id), ("binodex-real", shots_real)]
    global LANG
    vl = audio = sr = None
    if a.voice:
        vl, audio, sr = load_voice(a.voice)
        LANG = "ru" if a.voice.lower().endswith("_ru.json") else "kg"
    sfx = "-ru" if LANG == "ru" else ""                      # орусча: <ачкыч>-ru.mp4 (config.js → "<ачкыч>@ru")
    tmp_dir = os.path.dirname(os.path.abspath(a.voice)) if a.voice else OUT
    reader = Reader(a.src)
    for key, fn in jobs:
        if key in want:
            p = os.path.join(OUT, key + sfx + ".mp4")
            shots, wav = fn(), None
            if vl:
                shots, places, total = fit_voice(shots, GROUPS[key], vl)
                wav = os.path.join(tmp_dir, "_tmp_%s.wav" % key)
                voice_track(places, vl, audio, sr, total, wav)
            dur = render_video(reader, shots, p, a.debug, wav)
            if wav:
                os.remove(wav)
            print("%-17s %.1f с%s" % (key, dur, "" if a.debug else "  → %s (%d KB)" % (p, os.path.getsize(p) // 1024)))
    if "bot-id" in want:
        p = os.path.join(OUT, "bot-id" + sfx + ".mp4")
        warp, total, wav = None, 15.0, None
        if vl:
            warp, places, total = bot_warp(vl)
            wav = os.path.join(tmp_dir, "_tmp_bot-id.wav")
            voice_track(places, vl, audio, sr, total, wav)
        dur = render_bot(p, a.debug, warp, total, wav)
        if wav:
            os.remove(wav)
        print("%-17s %.1f с%s" % ("bot-id", dur, "" if a.debug else "  → %s (%d KB)" % (p, os.path.getsize(p) // 1024)))


if __name__ == "__main__":
    main()
