"""Сервердеги боттун жаңы каталарын алуу (aitrading.kg/api/errlog). Claude'дун мерчемдүү текшерүүсү ушуну иштетет.

    python tools/pull_errors.py          # жаңы каталар (JSON саптары); жок болсо — «NO_NEW_ERRORS»
    python tools/pull_errors.py --ack    # көрүлдү деп белгилөө (курсор алдыга жылат)

Ачкыч: ERRLOG_READ_KEY (Windows колдонуучунун чөйрө өзгөрмөсү; Ката_журналы_туташтыруу.bat коёт).
Абал: %LOCALAPPDATA%/aitrading/errlog_state.json — акыркы окулган id.
"""
import argparse
import json
import os
import sys
import urllib.request

SITE = (os.environ.get("SITE_URL") or "https://aitrading.kg").rstrip("/")
STATE = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "aitrading", "errlog_state.json")


def key():
    k = (os.environ.get("ERRLOG_READ_KEY") or "").strip()
    if not k and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = str(winreg.QueryValueEx(h, "ERRLOG_READ_KEY")[0]).strip()
        except OSError:
            pass
    return k


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"after": "", "pending": ""}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--ack", action="store_true")
    a = ap.parse_args()
    st = load()
    if a.ack:
        if st.get("pending"):
            st["after"], st["pending"] = st["pending"], ""
            save(st)
        print("ACKED", st["after"])
        return 0
    k = key()
    if not k:
        print("NO_KEY: ERRLOG_READ_KEY коюлган эмес — Ката_журналы_туташтыруу.bat иштетиңиз")
        return 2
    req = urllib.request.Request(SITE + "/api/errlog?after=" + st.get("after", ""), headers={"x-key": k, "User-Agent": "aitrading-errlog"})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.loads(r.read().decode("utf-8")).get("items") or []
    if not items:
        print("NO_NEW_ERRORS")
        return 0
    st["pending"] = items[-1]["id"]
    save(st)
    for it in items:
        print(json.dumps(it, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
