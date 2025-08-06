## Cloudflare UFW Firewall Setup

This guide explains how to configure and maintain a Cloudflare-based UFW firewall using the provided `update_cf_firewall.sh` script.

---

### Prerequisites

* Ubuntu (>= 18.04)
* `ufw` installed and enabled
* `curl` available on your system
* Root or sudo privileges

---

### 1. Deploy the Update Script

1. Copy the script to a system-wide location:

   ```bash
   sudo cp update_cf_firewall.sh /usr/local/bin/update_cf_firewall.sh
   ```

2. Ensure the file is owned by root and has secure permissions:

   ```bash
   sudo chown root:root /usr/local/bin/update_cf_firewall.sh
   sudo chmod 700 /usr/local/bin/update_cf_firewall.sh
   ```

3. Make the script executable:

   ```bash
   sudo chmod +x /usr/local/bin/update_cf_firewall.sh
   ```

---

### 2. Initial Run

Execute the script once to apply the initial firewall rules:

```bash
sudo /usr/local/bin/update_cf_firewall.sh
```

---

### 3. Verify UFW Status

Check that UFW is active and that Cloudflare ranges are allowed on HTTP/HTTPS:

```bash
sudo ufw status verbose
```

You should see entries similar to:

```
Status: active
...
80,443/tcp ALLOW IN from 198.51.100.0/24 # Cloudflare HTTP/S
```

---

### 4. Automate Updates with Cron

To keep the IP ranges in sync with Cloudflare, schedule the script to run daily:

1. Edit the root crontab:

   ```bash
   sudo crontab -e
   ```

2. Add the following line to run at 02:15 every day:

   ```cron
   15 2 * * * /usr/local/bin/update_cf_firewall.sh >> /var/log/cf_ufw_update_cron.log 2>&1
   ```

3. Save and exit. The script will now update the firewall and log its output daily.

---

### 5. Script Overview

Below is a summary of what `update_cf_firewall.sh` does:

1. **Fetch Cloudflare IP lists** from their official URLs (`ips-v4` and `ips-v6`).
2. **Acquire a lock** to prevent concurrent runs.
3. **Remove old Cloudflare rules** from UFW.
4. **Set UFW defaults** (deny incoming, allow outgoing).
5. **Allow SSH** on port 22.
6. **Whitelist all Cloudflare IPv4/IPv6 ranges** for HTTP (80) and HTTPS (443).
7. **Enable and reload** UFW to apply changes.
8. **Log** the update time.

For full details, refer to the script source in `update_cf_firewall.sh`.

---

### 6. Logs & Troubleshooting

* **Log file**: `/var/log/cf_ufw_update.log`
* **Cron log**: `/var/log/cf_ufw_update_cron.log`

If the script fails, inspect these logs for errors such as empty IP lists or UFW failures.
