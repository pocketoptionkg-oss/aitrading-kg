#!/usr/bin/env bash
# AITRADING.KG — Telegram-ботту серверге орнотуу (Ubuntu 22.04/24.04, Debian 12).
# Установка Telegram-бота на сервер. Запуск (с ПК): Сервер_орнотуу.bat  — или вручную:
#   scp deploy/server/install.sh root@IP:/root/install.sh
#   ssh -t root@IP "bash /root/install.sh"
# Кайра иштетсе болот (жаңыртат, эч нерсе бузулбайт). Можно запускать повторно.
#
# Что делает:
#   1) ставит git и Python, создаёт системного пользователя aitrading (без входа);
#   2) делает ключ «только чтение» для GitHub (deploy key) и клонирует репозиторий;
#   3) спрашивает токен Telegram и ключи BingX (на экране не видны) → /etc/aitrading/bot.env (600);
#   4) systemd: бот работает всегда и сам перезапускается; каждые 10 минут код обновляется из GitHub.
set -euo pipefail

REPO="${AITRADING_REPO:-git@github.com:pocketoptionkg-oss/aitrading-kg.git}"
HOME_DIR=/opt/aitrading
APP=$HOME_DIR/app
VENV=$HOME_DIR/venv
DATA=$HOME_DIR/data
ENVF=/etc/aitrading/bot.env
U=aitrading

say() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "root керек: sudo bash install.sh"; exit 1; }
as_u() { runuser -u "$U" -- env HOME="$HOME_DIR" "$@"; }   # aitrading колдонуучусунун атынан

say "1/6 Пакеттер (git, Python)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip ca-certificates tzdata openssh-client >/dev/null
timedatectl set-timezone Asia/Bishkek 2>/dev/null || true

say "2/6 Колдонуучу $U жана папкалар"
id "$U" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$HOME_DIR" --shell /usr/sbin/nologin "$U"
install -d -o "$U" -g "$U" -m 750 "$HOME_DIR" "$DATA"
install -d -o "$U" -g "$U" -m 700 "$HOME_DIR/.ssh"
install -d -m 755 /etc/aitrading
[ -f "$ENVF" ] || install -o "$U" -g "$U" -m 600 /dev/null "$ENVF"
chown "$U:$U" "$ENVF"; chmod 600 "$ENVF"
setdef() { grep -q "^$1=" "$ENVF" || echo "$1=$2" >> "$ENVF"; }
setdef SITE_URL https://aitrading-kg.pages.dev
setdef TG_LANG kg
setdef TG_DB "$DATA/tg_bot.db"

say "3/6 GitHub: окуу үчүн ачкыч (deploy key)"
KEY=$HOME_DIR/.ssh/id_ed25519
[ -f "$KEY" ] || as_u ssh-keygen -q -t ed25519 -N "" -C "aitrading-server" -f "$KEY"
as_u sh -c "ssh-keyscan -t ed25519 github.com >> $HOME_DIR/.ssh/known_hosts 2>/dev/null; sort -u -o $HOME_DIR/.ssh/known_hosts $HOME_DIR/.ssh/known_hosts"
until as_u git ls-remote "$REPO" HEAD >/dev/null 2>&1; do
  echo
  echo "Бул ачкычты GitHub'га кошуңуз / Добавьте этот ключ в GitHub:"
  echo "  https://github.com/pocketoptionkg-oss/aitrading-kg/settings/keys/new"
  echo "  Title: aitrading-server   ·   «Allow write access» — БЕЛГИЛЕБЕҢИЗ / НЕ отмечайте"
  echo
  cat "$KEY.pub"
  echo
  read -r -p "Кошкондон кийин Enter басыңыз (чыгуу: Ctrl+C)... " _
done
echo "GitHub ✓"

say "4/6 Код жана Python"
if [ -d "$APP/.git" ]; then
  as_u git -C "$APP" pull --ff-only -q
else
  as_u git clone -q "$REPO" "$APP"
fi
[ -x "$VENV/bin/python" ] || as_u python3 -m venv "$VENV"
as_u "$VENV/bin/pip" install -q --upgrade pip
as_u "$VENV/bin/pip" install -q numpy -r "$APP/tools/requirements.txt"
echo "Код: $(as_u git -C "$APP" log -1 --format='%h %s')"

say "5/6 Telegram жана BingX ачкычтары"
systemctl stop aitrading-bot 2>/dev/null || true      # setup getUpdates'ти колдонот — бот токтоп турсун
if grep -q '^TELEGRAM_BOT_TOKEN=' "$ENVF" && [ "${AITRADING_RESETUP:-}" != 1 ]; then
  echo "Ачкычтар мурунтан бар (кайра киргизүү: AITRADING_RESETUP=1 bash install.sh)."
else
  ( cd "$APP" && as_u AITRADING_ENV="$ENVF" bash -c "set -a; . '$ENVF'; set +a; exec '$VENV/bin/python' tools/tg_bot.py --setup" )     || warn "Туташтыруу толук бүткөн жок — кийин кайра: aitrading setup"
fi

say "6/6 systemd: бот + авто-жаңыртуу"
cat > /etc/systemd/system/aitrading-bot.service <<EOF
[Unit]
Description=AITRADING.KG Telegram bot (signals, registration, admin)
After=network-online.target
Wants=network-online.target

[Service]
User=$U
Group=$U
WorkingDirectory=$APP
EnvironmentFile=$ENVF
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/python tools/tg_bot.py
Restart=always
RestartSec=10
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cat > $HOME_DIR/update.sh <<EOF
#!/usr/bin/env bash
# GitHub'дан жаңыртуу; tools/ өзгөрсө — ботту кайра иштетүү
set -e
cd $APP
old=\$(runuser -u $U -- env HOME=$HOME_DIR git rev-parse HEAD)
runuser -u $U -- env HOME=$HOME_DIR git pull --ff-only -q || exit 0
new=\$(runuser -u $U -- env HOME=$HOME_DIR git rev-parse HEAD)
[ "\$old" = "\$new" ] && exit 0
if runuser -u $U -- env HOME=$HOME_DIR git diff --name-only "\$old" "\$new" | grep -q '^tools/requirements.txt'; then
  runuser -u $U -- env HOME=$HOME_DIR $VENV/bin/pip install -q numpy -r tools/requirements.txt
fi
if runuser -u $U -- env HOME=$HOME_DIR git diff --name-only "\$old" "\$new" | grep -q '^tools/.*\.py\$'; then
  systemctl restart aitrading-bot
  echo "updated \$old..\$new, bot restarted"
fi
EOF
chmod 755 $HOME_DIR/update.sh

cat > /etc/systemd/system/aitrading-update.service <<EOF
[Unit]
Description=AITRADING.KG: pull code from GitHub
After=network-online.target

[Service]
Type=oneshot
ExecStart=$HOME_DIR/update.sh
EOF

cat > /etc/systemd/system/aitrading-update.timer <<EOF
[Unit]
Description=AITRADING.KG: update every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
EOF

cat > /usr/local/bin/aitrading <<EOF
#!/usr/bin/env bash
# Кыска буйруктар: aitrading status | logs | restart | update | setup
case "\${1:-status}" in
  status)  systemctl --no-pager status aitrading-bot | head -15 ;;
  logs)    journalctl -u aitrading-bot -n 100 -f ;;
  restart) systemctl restart aitrading-bot && echo ok ;;
  update)  $HOME_DIR/update.sh; systemctl restart aitrading-bot; echo ok ;;
  setup)   AITRADING_RESETUP=1 bash /root/install.sh ;;
  *) echo "aitrading status|logs|restart|update|setup" ;;
esac
EOF
chmod 755 /usr/local/bin/aitrading

systemctl daemon-reload
systemctl enable --now aitrading-update.timer >/dev/null
if grep -q '^TELEGRAM_BOT_TOKEN=' "$ENVF"; then
  systemctl enable --now aitrading-bot >/dev/null
  sleep 4
  systemctl --no-pager --lines=8 status aitrading-bot || true
  say "Даяр! Бот иштеп жатат. / Готово, бот работает."
else
  warn "Токен жок — бот азырынча өчүк. Кийин: aitrading setup"
fi
echo "Буйруктар / Команды:  aitrading status | aitrading logs | aitrading restart | aitrading update | aitrading setup"
