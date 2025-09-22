Run this:

# Service unit
sudo tee /etc/systemd/system/cf-realip-sync.service >/dev/null <<'UNIT'
[Unit]
Description=Update Cloudflare real_ip ranges and reload nginx
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/cf-realip-sync
UNIT

# Timer unit (weekly, persistent, slight randomization)
sudo tee /etc/systemd/system/cf-realip-sync.timer >/dev/null <<'TIMER'
[Unit]
Description=Run cf-realip-sync weekly and at boot catch-up

[Timer]
OnCalendar=weekly
Persistent=true
RandomizedDelaySec=1h
Unit=cf-realip-sync.service

[Install]
WantedBy=timers.target
TIMER

sudo systemctl daemon-reload
sudo systemctl enable --now cf-realip-sync.timer
# Run once immediately:
sudo systemctl start cf-realip-sync.service

