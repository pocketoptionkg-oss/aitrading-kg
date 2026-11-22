"""Бир узун озвучканы (ElevenLabs) сценарийдин 17 сабына бөлүү → tools/voice/voice_<lang>.json (+ .wav).

    python tools/voice_split.py voice.mp3 --lang kg --cuts "4.16,6.06,…"   # 16 чек ара (болжол менен, секунда)
    python tools/voice_split.py voice.mp3 --lang ru --cuts "…" --verify       # ар бир кесиндини кайра таанып текшерүү

Чек араларды faster-whisper'дин сүйлөмдөрүнөн алабыз (саптар ортосундагы тыныгуулар); скрипт ар бирин ±0,2 с ичинде
үндүн эң тынч жерине такташат, саптын четиндеги тынчтыкты кесет (сөздү кеспей). --cuts жок болсо — тамга санына
жараша автоматтык болжол (тыныгуулары жок озвучкада ката болушу мүмкүн, --verify менен текшериңиз).
"""
import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_video_lessons import VOICE_SCRIPT  # noqa: E402


def load_wav(path, sr):
    out = path + ".tmp%d.wav" % sr
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(sr), out], check=True)
    with wave.open(out, "rb") as wf:
        a = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    os.remove(out)
    return a


def whisper_words(a16):
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a16, language="ru", word_timestamps=True, beam_size=5)   # кыргызча да орус модели менен таанылат
    return m, [(w.start, w.end, w.word) for s in segs for w in s.words]


def auto_cuts(words, lines):
    total = sum(len(l) for l in lines)
    t0, t1 = words[0][0], words[-1][1]
    gaps = [((words[i][1] + words[i + 1][0]) / 2, words[i + 1][0] - words[i][1]) for i in range(len(words) - 1)]
    cuts, acc = [], 0
    for k in range(len(lines) - 1):
        acc += len(lines[k])
        exp = t0 + (t1 - t0) * acc / total
        cand = [(abs(m - exp) - 2.5 * g, m) for m, g in gaps if not cuts or m > cuts[-1] + 0.3]
        cuts.append(min(cand)[1])
    return cuts


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--lang", default="kg", choices=["kg", "ru"])
    ap.add_argument("--cuts", help="16 чек ара, секунда, үтүр менен")
    ap.add_argument("--verify", action="store_true", help="ар бир кесиндини кайра таануу")
    a = ap.parse_args()
    lines = VOICE_SCRIPT[a.lang]
    a44 = load_wav(a.audio, 44100)
    dur = len(a44) / 44100
    hop = 441
    rms = np.sqrt(np.convolve(a44 ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    model = None
    if a.cuts:
        approx = [float(x) for x in a.cuts.split(",") if x.strip()]
    else:
        model, words = whisper_words(load_wav(a.audio, 16000))
        approx = auto_cuts(words, [t for _, t in lines])
    if len(approx) != len(lines) - 1:
        sys.exit("Чек ара %d болушу керек, берилди %d." % (len(lines) - 1, len(approx)))

    def quiet(t, win=0.2):
        i0, i1 = max(0, int((t - win) * 100)), min(len(rms) - 1, int((t + win) * 100))
        return (i0 + int(np.argmin(rms[i0:i1 + 1]))) / 100.0

    bounds = [0.0] + [quiet(t) for t in approx] + [dur]
    out = []
    for k, (key, text) in enumerate(lines):
        s, e = bounds[k], bounds[k + 1]
        seg = rms[int(s * 100):int(e * 100)]
        thr = seg.max() * 10 ** (-38 / 20) if len(seg) else 0
        loud = np.where(seg > thr)[0]
        if len(loud):
            s, e = max(s, s + loud[0] / 100 - 0.06), min(e, bounds[k] + loud[-1] / 100 + 0.14)
        out.append({"key": key, "start": round(s, 3), "end": round(e, 3), "text": text})
    if a.verify:
        from faster_whisper import WhisperModel
        model = model or WhisperModel("small", device="cpu", compute_type="int8")
    for l in out:
        line = "%-6s %6.2f–%6.2f (%.2f с)  %s" % (l["key"], l["start"], l["end"], l["end"] - l["start"], l["text"][:70])
        if a.verify:
            clip = load_wav(a.audio, 16000)[int(l["start"] * 16000):int(l["end"] * 16000)]
            segs, _ = model.transcribe(clip, language="ru", beam_size=5)
            line += "\n         таанылды: " + " ".join(s.text.strip() for s in segs)
        print(line)
    vdir = os.path.join(HERE, "voice")
    os.makedirs(vdir, exist_ok=True)
    wav = os.path.join(vdir, "voice_%s.wav" % a.lang)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.audio, "-ac", "1", "-ar", "44100", wav], check=True)
    with open(os.path.join(vdir, "voice_%s.json" % a.lang), "w", encoding="utf-8") as f:
        json.dump({"source": os.path.basename(a.audio), "wav": os.path.basename(wav), "cuts": approx, "lines": out}, f, ensure_ascii=False, indent=1)
    print("→", os.path.join(vdir, "voice_%s.json" % a.lang))


if __name__ == "__main__":
    main()
