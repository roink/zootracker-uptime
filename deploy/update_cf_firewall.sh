#!/usr/bin/env bash
set -eo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────────
export PATH=/usr/bin:/usr/sbin:/bin:/sbin
CF_IPV4_URL="https://www.cloudflare.com/ips-v4"
CF_IPV6_URL="https://www.cloudflare.com/ips-v6"
LOCKFILE=/var/lock/cf_ufw_update.lock
LOGFILE=/var/log/cf_ufw_update.log

# ─── Lock & Logging ────────────────────────────────────────────────────────────
exec 200>"$LOCKFILE"
flock -n 200 || exit 0
exec > >(tee -a "$LOGFILE") 2>&1

# ─── Temp Dir & Cleanup ─────────────────────────────────────────────────────────
TMP_DIR="$(mktemp -d /tmp/cf_ufw_update.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

# ─── Fetch IP Lists ─────────────────────────────────────────────────────────────
IPV4_LIST="$TMP_DIR/ips-v4.txt"
IPV6_LIST="$TMP_DIR/ips-v6.txt"

curl -fsSL --retry 3 --retry-delay 5 "$CF_IPV4_URL" -o "$IPV4_LIST"
curl -fsSL --retry 3 --retry-delay 5 "$CF_IPV6_URL" -o "$IPV6_LIST"

[[ -s "$IPV4_LIST" ]] || { echo "Empty IPv4 list"; exit 1; }
[[ -s "$IPV6_LIST" ]] || { echo "Empty IPv6 list"; exit 1; }

# ─── Remove Old Cloudflare Rules ────────────────────────────────────────────────
echo "Removing old Cloudflare UFW rules..."
ufw status numbered | awk '/Cloudflare HTTP\/S/ {print $1}' | \
  sed 's/\[//;s/\]//' | sort -rn | xargs -r ufw --force delete

# ─── Ensure Defaults & SSH ─────────────────────────────────────────────────────
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'

# ─── Whitelist New CF Ranges ───────────────────────────────────────────────────
echo "Adding IPv4 ranges..."
while read -r ip; do
  ufw allow proto tcp from "$ip" to any port 80,443 comment 'Cloudflare HTTP/S'
done < "$IPV4_LIST"

echo "Adding IPv6 ranges..."
while read -r ip; do
  ufw allow proto tcp from "$ip" to any port 80,443 comment 'Cloudflare HTTP/S'
done < "$IPV6_LIST"

# ─── Enable & Reload ───────────────────────────────────────────────────────────
ufw --force enable
ufw reload

echo "Update complete at $(date --iso-8601=seconds)"

