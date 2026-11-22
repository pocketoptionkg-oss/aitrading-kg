# -*- coding: utf-8 -*-
"""AITRADING.KG — сайтты телефондо ачуу (ошол эле Wi-Fi аркылуу) + QR-код.

Иштетүү:  Телефондо_ачуу.bat  (же: python tools/phone_qr.py)
  1) Компьютерде сайт серверин үйдөгү тармак үчүн ачат (порт 8770).
  2) Шилтемени жана QR-кодду көрсөтөт — телефондун камерасы менен сканерлейсиз.
  3) Терезени жапсаңыз — сервер токтойт.

Эскертүү: бул https эмес (үйдөгү тармак). Сайтты карап, анализаторду колдонсо болот,
бирок «тиркеме катары орнотуу» жана билдирмелер сайт https'те (aitrading.kg хостингде) гана иштейт.
Кошумча китепкана керек эмес: QR-код ушул жерде эсептелет, сүрөт — Pillow (болсо).
"""
import functools
import http.server
import os
import socket
import sys

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
OUT_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "телефон_QR.png")
PORTS = range(8770, 8780)
PAGE = "forecast.html?src=phone"


# ---------------------------------------------------------------- QR-код (байт режими, L деңгээли, 1–5 версия)
TOTAL = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134}
ECC = {1: 7, 2: 10, 3: 15, 4: 20, 5: 26}


def _mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _divisor(deg):
    res = [0] * (deg - 1) + [1]
    root = 1
    for _ in range(deg):
        for j in range(deg):
            res[j] = _mul(res[j], root)
            if j + 1 < deg:
                res[j] ^= res[j + 1]
        root = _mul(root, 2)
    return res


def _remainder(data, div):
    res = [0] * len(div)
    for b in data:
        f = b ^ res.pop(0)
        res.append(0)
        for i, c in enumerate(div):
            res[i] ^= _mul(c, f)
    return res


def _mask(m, x, y):
    return [
        (x + y) % 2 == 0, y % 2 == 0, x % 3 == 0, (x + y) % 3 == 0,
        (x // 3 + y // 2) % 2 == 0, x * y % 2 + x * y % 3 == 0,
        (x * y % 2 + x * y % 3) % 2 == 0, ((x + y) % 2 + x * y % 3) % 2 == 0,
    ][m]


def qr_matrix(text):
    data = text.encode("utf-8")
    ver = next((v for v in TOTAL if 12 + 8 * len(data) <= (TOTAL[v] - ECC[v]) * 8), None)
    if ver is None:
        raise ValueError("Шилтеме өтө узун")
    cap = (TOTAL[ver] - ECC[ver]) * 8
    bits = []

    def add(val, n):
        bits.extend((val >> i) & 1 for i in range(n - 1, -1, -1))

    add(4, 4)
    add(len(data), 8)
    for b in data:
        add(b, 8)
    add(0, min(4, cap - len(bits)))
    add(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        add(pad, 8)
        pad ^= 0xEC ^ 0x11
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    allcw = cw + _remainder(cw, _divisor(ECC[ver]))

    size = ver * 4 + 17
    M = [[False] * size for _ in range(size)]
    F = [[False] * size for _ in range(size)]

    def setf(x, y, d):
        M[y][x] = d
        F[y][x] = True

    for i in range(size):
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    if ver >= 2:
        p = size - 7
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                setf(p + dx, p + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask):
        d = (1 << 3) | mask  # L = 01
        rem = d
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        fb = ((d << 10) | rem) ^ 0x5412
        g = lambda i: (fb >> i) & 1 == 1
        for i in range(6):
            setf(8, i, g(i))
        setf(8, 7, g(6))
        setf(8, 8, g(7))
        setf(7, 8, g(8))
        for i in range(9, 15):
            setf(14 - i, 8, g(i))
        for i in range(8):
            setf(size - 1 - i, 8, g(i))
        for i in range(8, 15):
            setf(8, size - 15 + i, g(i))
        setf(8, size - 8, True)

    draw_format(0)  # орунду ээлеп коюу
    i, total = 0, len(allcw) * 8
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not F[y][x] and i < total:
                    M[y][x] = ((allcw[i >> 3] >> (7 - (i & 7))) & 1) == 1
                    i += 1
        right -= 2

    def penalty(A):
        p = 0
        for rows in (A, [list(c) for c in zip(*A)]):
            for row in rows:
                run = 1
                for k in range(1, size):
                    if row[k] == row[k - 1]:
                        run += 1
                    else:
                        if run >= 5:
                            p += run - 2
                        run = 1
                if run >= 5:
                    p += run - 2
                s = "".join("1" if c else "0" for c in row)
                p += 40 * (s.count("10111010000") + s.count("00001011101"))
        for y in range(size - 1):
            for x in range(size - 1):
                if A[y][x] == A[y][x + 1] == A[y + 1][x] == A[y + 1][x + 1]:
                    p += 3
        dark = sum(map(sum, A))
        p += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
        return p

    base = [row[:] for row in M]
    best = None
    for m in range(8):
        for y in range(size):
            for x in range(size):
                M[y][x] = base[y][x] ^ (not F[y][x] and _mask(m, x, y))
        draw_format(m)
        sc = penalty(M)
        if best is None or sc < best[0]:
            best = (sc, [row[:] for row in M])
    return best[1]


def save_png(M, path, caption):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    n, s, q = len(M), 12, 4
    w = (n + 2 * q) * s
    img = Image.new("RGB", (w, w + 70), "white")
    d = ImageDraw.Draw(img)
    for y in range(n):
        for x in range(n):
            if M[y][x]:
                d.rectangle([(x + q) * s, (y + q) * s, (x + q + 1) * s - 1, (y + q + 1) * s - 1], fill="black")
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for k, line in enumerate(caption):
        tw = d.textlength(line, font=font)
        d.text(((w - tw) / 2, w - 6 + k * 24), line, fill="black", font=font)
    img.save(path)
    return True


def print_qr(M):
    n, q = len(M), 2
    rows = [[False] * (n + 2 * q) for _ in range(q)] + [[False] * q + r + [False] * q for r in M] + [[False] * (n + 2 * q) for _ in range(q)]
    # Консолдун фону кара: ак модулдарды «█» менен чийебиз (2 сапты 1 сапка: ▀ ▄)
    for y in range(0, len(rows), 2):
        a, b = rows[y], rows[y + 1] if y + 1 < len(rows) else [True] * len(rows[0])
        print("".join("█" if not t and not u else "▀" if not t else "▄" if not u else " " for t, u in zip(a, b)))


# ---------------------------------------------------------------- Сервер
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # пакет жөнөтүлбөйт — жөн гана тармак картасын тандоо
        return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.path.split("?")[0].endswith(".html") or self.path == "/":
            print("  📱 {} ачты: {}".format(self.client_address[0], self.path))

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main(test=False):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ip = lan_ip()
    httpd = None
    for port in PORTS:
        try:
            # --test: текшерүү үчүн компьютердин ичинде гана (тармакка ачылбайт, сүрөт ачылбайт)
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1" if test else "0.0.0.0", port), functools.partial(Handler, directory=os.path.abspath(SITE)))
            break
        except OSError:
            continue
    if httpd is None:
        print("8770–8779 порттору бош эмес. Башка терезелерди жаап, кайра аракет кылыңыз.")
        return
    url = "http://{}:{}/{}".format(ip, port, PAGE)
    M = qr_matrix(url)
    print()
    print("  AITRADING.KG — телефондо ачуу")
    print("  ─────────────────────────────")
    print("  1) Телефон ушул компьютер менен БИР Wi-Fi'да болушу керек.")
    print("  2) Телефондун камерасы менен QR-кодду сканерлеңиз же шилтемени териңиз:")
    print()
    print("     " + url)
    print()
    if save_png(M, OUT_PNG, [url, "Телефондун камерасы менен сканерлеңиз"]):
        print("  QR-код сүрөтү: " + os.path.abspath(OUT_PNG))
        try:
            if not test:
                os.startfile(os.path.abspath(OUT_PNG))
        except Exception:
            pass
    else:
        print_qr(M)
    print()
    print("  Windows «Брандмауэр» суроо берсе — «Частные сети» белгилеп, «Разрешить» басыңыз.")
    print("  Эскертүү: бул https эмес — тиркеме орнотуу жана билдирмелер сайт хостингге чыккандан кийин иштейт.")
    print("  Токтотуу үчүн — бул терезени жабыңыз.")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--png":
        # Текшерүү үчүн: python phone_qr.py --png "<текст>" <file.png>
        save_png(qr_matrix(sys.argv[2]), sys.argv[3], [sys.argv[2]])
    else:
        main(test="--test" in sys.argv)
