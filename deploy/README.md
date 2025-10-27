# Deployment Directory README

This directory contains all the files and configuration templates needed to deploy the Zoo Tracker application to a Hetzner VM. It is designed to let you build and push your code and configuration from your local development machine.

## Contents

* **deploy\_zootracker.sh**
  A Bash script to automate the deployment process:

  1. Installs required packages on the remote VM.
  2. Generates secure database credentials and application secret keys.
  3. Uses `rsync` to copy your project source code (excluding `venv`, `.git`, and other build artifacts) to `/opt/zoo_tracker` on the VM.
  4. Creates a Python virtual environment, installs dependencies, and sets up the `.env` file on the VM.
  5. Builds the React/Vite frontend locally and synchronizes the static files to `/var/www/zootracker`.
  6. Copies the pre-made systemd service unit and nginx site configuration to the VM.
  7. Reloads systemd, enables and starts the API service, tests and reloads nginx, and issues a Let’s Encrypt certificate.

* **setup-cloudflare-realip.yml**
  An Ansible playbook that installs the `cf-realip-sync` helper under `/usr/local/sbin/`, generates `/etc/nginx/conf.d/20-cloudflare-realip.conf`,
  and configures the matching `cf-realip-sync.service`/`.timer` so nginx always recognizes the correct client IP addresses when running behind Cloudflare.

* **setup-cloudflare-firewall.yml**
  An Ansible playbook that installs UFW, deploys the Cloudflare-aware allow-list script, and enables a systemd timer so the firewall stays in sync with Cloudflare's published IPv4/IPv6 ranges. Requires the `community.general` collection.

* **setup-zoo-tracker-service.yml**
  An Ansible playbook that deploys the Zoo Tracker systemd unit together with the hardening and logging drop-ins in `/etc/systemd/system/zoo_tracker.service.d/` and the matching logrotate policy under `/etc/logrotate.d/zootracker`.

* **templates/zoo\_tracker.service.j2**
  A systemd unit template for running the FastAPI backend under `gunicorn + uvicorn` bound to `127.0.0.1:8000` with loopback forwarding enabled.

* **templates/zootracker-service-hardening.conf.j2**
  A systemd drop-in template that enables strict sandboxing and read-only filesystem access for the service.

* **templates/zootracker-service-logs.conf.j2**
  A systemd drop-in template that provisions dedicated log directories and environment variables for raw/anonymized streams.

  The service enables Uvicorn proxy header parsing so `request.client.host` is
  the real client IP (behind Nginx on loopback), which is important for rate
  limiting and observability.

* **templates/zootracker.logrotate.j2**
  A logrotate policy template that keeps raw logs for 30 days and anonymized logs indefinitely (subject to disk monitoring).

* **zoo\_tracker.nginx**
  An nginx server block to serve static files from `/var/www/zootracker` and proxy `/api/` requests to the FastAPI backend. Place in `/etc/nginx/sites-available/` and symlink to `sites-enabled/`.

## Prerequisites

1. **Local machine**:

   * `bash`, `rsync`, `ssh`, `scp`, `openssl`, `npm` installed.
   * Your project root contains the `frontend/`, `app/`, `requirements.txt`, etc.
   * This `deploy/` directory is inside your project tree.

2. **Remote VM**:

   * Ubuntu 22.04 LTS.
   * A non-root user with `sudo` privileges (default user: `philipp`).
   * Port 22 open for SSH, ports 80/443 for HTTP/HTTPS.
   * Cloudflare's **Add visitor location headers** Managed Transform enabled for the
     zone so the API receives `cf-iplatitude`/`cf-iplongitude` headers used by the
     `/location/estimate` endpoint.

## Cloudflare DNS credentials

Certbot now uses the Cloudflare DNS-01 plugin so TLS renewals succeed even when the site is fully locked down behind the Cloudflare firewall. Create a restricted API token and store it with Ansible Vault before running `setup-nginx.yml`:

1. In the Cloudflare dashboard open **My Profile → API Tokens → Create Token**.
2. Start from the **Edit zone DNS** template, then restrict the token to the Zoo Tracker zone only.
3. Copy the generated token string.
4. Encrypt it in `deploy/group_vars/zoo_server.vault.yml`:

   ```bash
   ansible-vault create deploy/group_vars/zoo_server.vault.yml
   ```

5. Add the following YAML to the vault file and save:

   ```yaml
   vault_cloudflare_api_token: "<paste-the-token>"
   ```

6. When running any playbook that touches nginx/Certbot, include the vault password (e.g. `ansible-playbook setup-nginx.yml --ask-vault-pass`). The playbook asserts that `cloudflare_api_token` is set, so the run will fail fast if the credentials are missing.

## Verifying the firewall

Run the playbook with:

```bash
ansible-playbook -i inventory.ini setup-cloudflare-firewall.yml
```

> **Dependency:** Install the `community.general` collection first if it is not already present: `ansible-galaxy collection install community.general`.

After applying `setup-cloudflare-firewall.yml`, confirm that the expected rules are present:

```bash
sudo ufw status verbose     # ensure Status: active and see defaults/comments
sudo ufw status numbered    # verify Cloudflare HTTP/S rules are present
```

To check the timer and logs:

```bash
systemctl list-timers cf-ufw-sync.timer
journalctl -u cf-ufw-sync.service --since today
```

> **ACME note:** DNS-01 validation works with proxied (orange-cloud) records, so there is no need to grey-cloud the zone for certificate issuance. If you fall back to HTTP-01 for any reason, remember that direct Let’s Encrypt probes bypass Cloudflare and will be blocked unless you temporarily relax the firewall.

## Usage

From your project root, run:

```bash
chmod +x deploy/deploy_zootracker.sh
./deploy/deploy_zootracker.sh <REMOTE_IP> <DOMAIN>
```

Example:

```bash
./deploy/deploy_zootracker.sh 138.199.203.214 www.ZooTracker.app
```

The script will display the generated **database password** and **SECRET\_KEY** at
the end. Store these securely and update any existing `.env` files or
orchestration tooling with the new `DATABASE_URL` value so the service never
falls back to shared credentials. Ensure your production environment exports
`APP_ENV=production` (the default) so placeholder credentials are rejected at
startup.

> **Important:** The backend refuses to start unless `SECRET_KEY` is present in `.env`. Generate a long, random value such as
> `openssl rand -hex 32` (64 hex characters = 32 bytes) before launching the service, and rotate it regularly. Weak or short
> secrets let attackers brute-force HS256 JWTs, so never rely on guessable placeholders.

## Customization

* **REMOTE\_USER** and **SSH\_TARGET** are hardcoded in the script as `philipp@<REMOTE_IP>`. Modify if your server username or host differs.
* **APP\_DIR** (`/opt/zoo_tracker`) and **WEB\_ROOT** (`/var/www/zootracker`) can be changed in the script to suit your environment.
* Edit `zoo_tracker.service` or `zoo_tracker.nginx` templates if you need extra configuration (logging paths, worker counts, SSL settings, etc.).

### PostgreSQL configuration

Tune PostgreSQL with the same defaults used in development. Append the
following block to `/etc/postgresql/15/main/postgresql.conf` (adjust the path
for your distribution) and restart the database service:

```
max_connections = 200
shared_buffers = 1GB
effective_cache_size = 3GB
maintenance_work_mem = 256MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 5041kB
huge_pages = off
min_wal_size = 1GB
max_wal_size = 4GB
```

These values mirror the container bootstrap script under `docker/db/init/` so
production and development behave consistently.

### Dual logging streams & logrotate

The drop-in `zootracker-service-logs.conf` sets two environment variables so the
app writes ECS JSON to both an anonymized file (`LOG_FILE_ANON`) and a short-term
raw file (`LOG_FILE_RAW`). Systemd creates `/var/log/zoo-tracker/anon` and
`/var/log/zoo-tracker/raw` with `0750` permissions at start-up, allowing only the
service account and administrators to read archived entries. The
`setup-zoo-tracker-service.yml` playbook installs the accompanying
`templates/zootracker.logrotate.j2` snippet to `/etc/logrotate.d/zootracker` so
retention is managed automatically; adjust the template before running the
playbook if different retention windows are required. The playbook validates the
configuration with `logrotate -d` when the template changes, and the existing
systemd timer/cron will pick up the new policy automatically. Because the
application uses `WatchedFileHandler` it will automatically reopen files after
logrotate moves them aside; no service restart is required. Adjust the `create`
owner/group to match the system user that runs Gunicorn (for the provided unit
file this is `www-data`).

## Troubleshooting

* **Systemd service fails**: Check `journalctl -u zoo_tracker -e` on the server.
* **nginx errors**: Run `sudo nginx -t` and inspect `/var/log/nginx/error.log`.
* **Certificate issues**: Ensure DNS for `<DOMAIN>` points to `<REMOTE_IP>` before requesting with Certbot.


