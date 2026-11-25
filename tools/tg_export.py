"""AITRADING.KG — заявкалар жана бот колдонуучулары PDF'ке (ээсине гана жөнөтүлөт).

Текст PDF'те чыныгы текст болуп калат (номерди көчүрүүгө болот). Шрифт — matplotlib'дин DejaVu Sans (кириллица бар).
"""
import io
from datetime import datetime, timedelta, timezone

BISHKEK = timezone(timedelta(hours=6))
ROWS = 34                                   # бир беттеги сап


def _t(ms, fmt="%d.%m.%Y %H:%M"):
    return datetime.fromtimestamp(ms / 1000, BISHKEK).strftime(fmt) if ms else "—"


def _cut(s, n):
    s = str(s if s not in (None, "") else "—")
    return s if len(s) <= n else s[:n - 1] + "…"


def build(leads, users, st_names, title="AITRADING.KG"):
    """leads: [{t, name, wa, broker, src, page, country, username, tg_id}], users: [{...users row}]. Кайтарат: PDF байттары."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    br = {"bingx": "BingX", "binodex": "BinoDex", "admin": "admin"}
    sec = [
        ("Заявки WhatsApp", [("№", .04), ("Дата и время", .08), ("Имя", .25), ("WhatsApp", .41), ("Telegram", .58), ("ID", .76), ("Брокер", .88)],
         [(i, _t(x.get("t")), _cut(x.get("name"), 18), x.get("wa") or "—", ("@" + x["username"]) if x.get("username") else "—",
           x.get("tg_id") or "—", br.get(x.get("broker"), "—") + (" · " + x["src"] if x.get("src") else ""))
          for i, x in enumerate(leads, 1)]),
        ("Клиенты бота", [("№", .04), ("Пришёл", .08), ("Имя", .23), ("Telegram", .38), ("ID", .55), ("Статус", .67), ("WhatsApp", .82)],
         [(i, _t(u.get("created"), "%d.%m.%Y"), _cut(u.get("first_name"), 16), _cut(("@" + u["username"]) if u.get("username") else "—", 20),
           u["id"], _cut(st_names.get(u.get("status"), u.get("status")), 16), u.get("wa") or "—")
          for i, u in enumerate(users, 1)]),
    ]
    now = datetime.now(BISHKEK).strftime("%d.%m.%Y %H:%M")
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for name, cols, rows in sec:
            pages = [rows[i:i + ROWS] for i in range(0, len(rows), ROWS)] or [[]]
            for pn, chunk in enumerate(pages, 1):
                fig = plt.figure(figsize=(8.27, 11.69))
                fig.text(.04, .965, "%s — %s" % (title, name), fontsize=14, weight="bold")
                fig.text(.04, .945, "Всего: %d · выгрузка %s (Бишкек) · стр. %d/%d · конфиденциально" % (len(rows), now, pn, len(pages)),
                         fontsize=8, color="#555555")
                y = .915
                for h, x in cols:
                    fig.text(x, y, h, fontsize=8, weight="bold")
                fig.add_artist(plt.Line2D([.04, .96], [y - .006, y - .006], color="#999999", lw=.6))
                y -= .025
                for k, r in enumerate(chunk):
                    if k % 2 == 0:
                        fig.add_artist(plt.Rectangle((.035, y - .007), .93, .024, color="#f1f3f6", lw=0, zorder=0))
                    for (h, x), v in zip(cols, r):
                        fig.text(x, y, str(v), fontsize=7.6)
                    y -= .025
                if not chunk:
                    fig.text(.04, y, "Пока пусто.", fontsize=9, color="#777777")
                pdf.savefig(fig)
                plt.close(fig)
    return buf.getvalue()


if __name__ == "__main__":                     # үлгү: python tg_export.py out.pdf
    import sys
    import time
    ms = int(time.time() * 1000)
    L = [{"t": ms - i * 3600000, "name": "Мырза %d" % i, "wa": "+99670989339%d" % (i % 10), "broker": "binodex", "src": "site",
          "username": "user%d" % i if i % 3 else None, "tg_id": 500000 + i if i % 2 else None} for i in range(40)]
    U = [{"id": 600000 + i, "created": ms - i * 86400000, "first_name": "Айбек", "username": "aibek%d" % i, "status": "new", "wa": None} for i in range(5)]
    open(sys.argv[1], "wb").write(build(L, U, {"new": "Регистрация не завершена"}))
    print("ok")
