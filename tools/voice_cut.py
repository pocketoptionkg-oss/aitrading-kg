"""ElevenLabs'тен бир узун озвучканы (фразалар тыныгуу менен) сайттын mp3 фразаларына бөлүү.

    python tools/voice_cut.py voice.mp3 --lang ky --keys hello,load,... [--noise -30 --dur 0.35] [--check]

Тыныгууларды ffmpeg silencedetect менен табат, ар бир тыныгуунун ортосунан кесет,
site/assets/audio/<lang>/<key>.mp3 кылып сактайт (четтериндеги тынчтык кесилет, 64 kbps моно).
--check: ар бир кесиндини faster-whisper менен кайра таанып, tools/bot_voice_phrases.csv'деги текст менен салыштырат.
"""
import argparse
import csv
import difflib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(os.path.dirname(HERE), "site", "assets", "audio")


def silences(path, noise, dur):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "silencedetect=noise=%sdB:d=%s" % (noise, dur), "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(st, en))


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode().strip())


def norm(s):
    return re.sub(r"[^\w]+", " ", s.lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--lang", required=True, choices=["ky", "ru"])
    ap.add_argument("--keys", required=True)
    ap.add_argument("--noise", default="-30")
    ap.add_argument("--dur", default="0.2")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--csv", default="bot_voice_phrases.csv", help="tools/ ичиндеги фразалар файлы")
    ap.add_argument("--bounds", help="чек араларды кол менен берүү, секунда")
    ap.add_argument("--out", help="башка папкага сактоо (демейки site/assets/audio/<lang>)")
    a = ap.parse_args()
    keys = a.keys.split(",")
    total = duration(a.audio)
    sil = [s for s in silences(a.audio, a.noise, a.dur) if s[0] > 0.05 and s[1] < total - 0.05]
    col = "text_ky" if a.lang == "ky" else "text_ru"
    texts = {}
    for r in csv.DictReader(io.open(os.path.join(HERE, a.csv), encoding="utf-8-sig"), delimiter=";"):
        texts[r["key"]] = r[col]
    # Чек араларды тандоо (DP): фразанын узундугу (тамга саны) боюнча күтүлгөн чек арага эң жакын, узунураак тыныгуулар
    w = [len(texts.get(k, "x")) + 6 for k in keys]
    cum, acc = [], 0
    for x in w[:-1]:
        acc += x
        cum.append(total * acc / sum(w))
    cand = [((s + e) / 2, e - s) for s, e in sil]
    n, m = len(cum), len(cand)
    if m < n:
        print("! тыныгуу %d, керек %d — --dur кичирейтиңиз" % (m, n))
        sys.exit(1)
    INF = float("inf")
    cost = lambda i, j: (cand[j][0] - cum[i]) ** 2 - 2.0 * min(cand[j][1], 1.5)
    dp = [[INF] * m for _ in range(n)]
    back = [[-1] * m for _ in range(n)]
    for j in range(m):
        dp[0][j] = cost(0, j)
    for i in range(1, n):
        best, bj = INF, -1
        for j in range(m):
            if j > 0 and dp[i - 1][j - 1] < best:
                best, bj = dp[i - 1][j - 1], j - 1
            if bj >= 0:
                dp[i][j] = best + cost(i, j)
                back[i][j] = bj
    j = min(range(m), key=lambda x: dp[n - 1][x])
    picks = []
    for i in range(n - 1, -1, -1):
        picks.append(cand[j][0])
        j = back[i][j]
    bounds = [0.0] + sorted(picks) + [total]
    out_dir = a.out or os.path.join(AUDIO, a.lang)
    os.makedirs(out_dir, exist_ok=True)
    if a.bounds:                                  # кол менен: --bounds "6.67,8.54,…" (len(keys)-1 чек ара)
        bounds = [0.0] + [float(x) for x in a.bounds.split(",")] + [total]
    if a.check:
        import numpy as np
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8")
    for i, k in enumerate(keys):
        dst = os.path.join(out_dir, k + ".mp3")
        af = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.08"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % bounds[i], "-to", "%.3f" % bounds[i + 1], "-i", a.audio,
                        "-af", af, "-ac", "1", "-ar", "44100", "-b:a", "64k", dst], check=True)
        line = "%-12s %5.2f–%5.2f" % (k, bounds[i], bounds[i + 1])
        if a.check:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", dst, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
            segs, _ = model.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0, language="ru", beam_size=1)   # PyAV эски — numpy
            heard = " ".join(s.text for s in segs)
            sim = difflib.SequenceMatcher(None, norm(heard), norm(texts.get(k, ""))).ratio()
            line += "  %3d%%  %s" % (sim * 100, heard.strip()[:60])
        print(line)


if __name__ == "__main__":
    main()
