"""AITRADING.KG сайтынын сүрөттөрүн даярдоо (бир жолу иштетилет).

    python tools/make_images.py

Чыгат (site/assets/img):
  * author.webp        — автордун сүрөтү, ак фон алынган, ак контур менен (900 px)
  * binodex-logo.png   — BinoDex логотиби: белги вектор менен, сөз бөлүшүү картасынан
  * og-image.jpg       — соцтармактар үчүн превью 1200x630

Булактар (өзгөртүлбөйт, окулат гана):
  * Превью_Партнёрдук_программа/src/cache/person_cut.png  (IMG_1024.psd'ден кесилген)
  * D:\\Загрузки\\Картинки\\binodex-pnl-CL-1792155460943.jpg
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "site")
OUT = os.path.join(SITE, "assets", "img")
PROJECT = os.path.dirname(os.path.dirname(HERE))
PERSON = os.path.join(PROJECT, "Превью_Партнёрдук_программа", "src", "cache", "person_cut.png")
BNX_CARD = r"D:\Загрузки\Картинки\binodex-pnl-CL-1792155460943.jpg"

YELLOW = (255, 204, 21)
MINT = (92, 232, 170)
BG = (8, 12, 20)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def author():
    im = Image.open(PERSON).convert("RGBA")
    im = im.crop((0, 980, 3024, 4032))                  # баш үстүндө аз гана боштук
    w = 900
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    a = np.asarray(im.getchannel("A")).astype(np.float32) / 255
    # ак контур: альфаны кеңейтип, ак түс менен толтурабыз
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    ring = cv2.dilate(a, k)
    ring = cv2.GaussianBlur(ring, (0, 0), 1.0)
    base = Image.new("RGBA", im.size, (255, 255, 255, 0))
    base.putalpha(Image.fromarray((ring * 255).astype(np.uint8)))
    base.alpha_composite(im)
    base.save(os.path.join(OUT, "author.webp"), quality=86, method=6)
    return im


def binodex_logo():
    """Бул функция Превью_Партнёрдук_программа/src/build_thumb.py'дан көчүрүлгөн."""
    card = np.asarray(Image.open(BNX_CARD).convert("RGB")).astype(np.float32)
    X0, Y0, X1, Y1 = 40, 1036, 266, 1114
    S = 8
    reg = card[Y0:Y1, X0:X1]
    lum = reg.mean(2)
    bg = np.median(lum)
    v = np.clip((lum - bg) / (250 - bg), 0, 1)
    v[:, :62] = 0
    big = cv2.resize(v, ((X1 - X0) * S, (Y1 - Y0) * S), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), 3.0)
    word = smoothstep(0.47, 0.64, big)
    mint = card[1050:1059, 65:74].reshape(-1, 3)
    mint = mint[mint[:, 1].argmax()]
    hh, ww = word.shape
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    icon_a = np.zeros_like(word)
    icon_c = np.zeros((hh, ww, 3), np.float32)
    rad = 6.0 * S
    for (sx, sy), (ex, ey) in [((69.5, 1054.0), (83.75, 1075.5)), ((68.75, 1096.75), (53.75, 1070.5))]:
        sx, sy, ex, ey = (sx - X0) * S, (sy - Y0) * S, (ex - X0) * S, (ey - Y0) * S
        dx, dy = ex - sx, ey - sy
        L2 = dx * dx + dy * dy
        t = np.clip(((xx - sx) * dx + (yy - sy) * dy) / L2, 0, 1)
        dist = np.hypot(xx - (sx + t * dx), yy - (sy + t * dy))
        inside = np.clip((rad - dist) / 2.0 + 0.5, 0, 1)
        alpha = inside * (1 - 0.55 * smoothstep(0.10, 1.0, t))
        col = mint * (1 - 0.45 * t[..., None]) + np.array([30, 120, 90]) * 0.45 * t[..., None]
        icon_c = icon_c * (1 - alpha[..., None]) + col * alpha[..., None]
        icon_a = icon_a + alpha * (1 - icon_a)
    A = np.clip(icon_a + word, 0, 1)
    rgb = (icon_c * icon_a[..., None] + 255 * word[..., None] * (1 - icon_a[..., None])) / np.maximum(A, 1e-4)[..., None]
    im = Image.fromarray(np.dstack([rgb.clip(0, 255), A * 255]).astype(np.uint8), "RGBA")
    im = im.crop(im.getbbox())
    h = 120
    im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    im.save(os.path.join(OUT, "binodex-logo.png"), optimize=True)
    return im


def font(name, size):
    return ImageFont.truetype(os.path.join(r"C:\Windows\Fonts", name), size)


def og_image(person, logo):
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    # жумшак жарык тактар
    glow = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(glow)
    g.ellipse((700, -120, 1320, 520), fill=(70, 56, 8))
    g.ellipse((-200, 360, 420, 900), fill=(14, 64, 48))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 1.0)
    d = ImageDraw.Draw(img)
    # тор сызыктар
    for x in range(0, W, 60):
        d.line((x, 0, x, H), fill=(16, 22, 34))
    for y in range(0, H, 60):
        d.line((0, y, W, y), fill=(16, 22, 34))
    # автор
    p = Image.open(os.path.join(OUT, "author.webp")).convert("RGBA")
    ph = 600
    p = p.resize((round(p.width * ph / p.height), ph), Image.LANCZOS)
    img.paste(p, (W - p.width + 40, H - ph + 30), p)
    # текст
    # бренд: [AI] TRADING.KG
    fb = font("segoeuib.ttf", 78)
    d.rounded_rectangle((64, 150, 64 + 104, 150 + 96), 18, fill=MINT)
    d.text((80, 152), "AI", font=fb, fill=(4, 23, 15))
    d.text((184, 152), "TRADING", font=fb, fill=(255, 255, 255))
    tw = d.textlength("TRADING", font=fb)
    d.text((184 + tw, 152), ".KG", font=fb, fill=YELLOW)
    d.text((66, 84), "TRADER KG · Нурсултан", font=font("segoeuib.ttf", 30), fill=YELLOW)
    f2 = font("segoeuisl.ttf", 34)
    d.text((66, 276), "Трейдингдеги окуяларды талдоо жана прогноз", font=f2, fill=(220, 226, 236))
    d.text((66, 322), "Жаңылыктар · ИИ-прогноз · Анализатор · Окуу", font=f2, fill=(220, 226, 236))
    lg = logo.resize((round(logo.width * 50 / logo.height), 50), Image.LANCZOS)
    d.rounded_rectangle((64, 410, 64 + lg.width + 44, 410 + 80), 18, outline=MINT, width=3, fill=(10, 20, 22))
    img.paste(lg, (86, 425), lg)
    bx = 64 + lg.width + 44 + 18
    fx = font("segoeuib.ttf", 44)
    bw = d.textlength("BingX", font=fx)
    d.rounded_rectangle((bx, 410, bx + bw + 48, 490), 18, outline=(59, 123, 255), width=3, fill=(10, 14, 30))
    d.text((bx + 24, 420), "Bing", font=fx, fill=(255, 255, 255))
    d.text((bx + 24 + d.textlength("Bing", font=fx), 420), "X", font=fx, fill=(59, 123, 255))
    d.text((66, 540), "18+  Соода тобокелдиктүү. Киреше кепилденбейт.", font=font("segoeui.ttf", 24), fill=(150, 160, 175))
    img.save(os.path.join(OUT, "og-image.jpg"), quality=88, optimize=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    person = author()
    logo = binodex_logo()
    og_image(person, logo)
    for n in sorted(os.listdir(OUT)):
        print(n, os.path.getsize(os.path.join(OUT, n)) // 1024, "KB")
