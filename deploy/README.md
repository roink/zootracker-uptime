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

* **zoo\_tracker.service**
  A systemd unit file for running the FastAPI backend under `gunicorn + uvicorn` bound to `127.0.0.1:8000`. Place in `/etc/systemd/system/` on the server.

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
service account and administrators to read archived entries.

To keep retention aligned with GDPR while preserving security evidence, install
a logrotate policy under `/etc/logrotate.d/zootracker`:

```conf
# 1) RAW logs — delete after ~30 days
/var/log/zoo-tracker/raw/*.log {
    daily
    dateext
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    rotate 30
    maxage 30
}

# 2) ANONYMIZED logs — keep indefinitely (monitor disk usage)
/var/log/zoo-tracker/anon/*.log {
    weekly
    dateext
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    rotate 9999
}
```

Reload logrotate (`sudo systemctl reload logrotate`) after placing the snippet
so new rotations take effect. Because the application uses `WatchedFileHandler`
it will automatically reopen files after logrotate moves them aside; no service
restart is required. Adjust the `create` owner/group to match the system user
that runs Gunicorn (for the provided unit file this is `www-data`).

## Troubleshooting

* **Systemd service fails**: Check `journalctl -u zoo_tracker -e` on the server.
* **nginx errors**: Run `sudo nginx -t` and inspect `/var/log/nginx/error.log`.
* **Certificate issues**: Ensure DNS for `<DOMAIN>` points to `<REMOTE_IP>` before requesting with Certbot.


