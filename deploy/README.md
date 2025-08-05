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

The script will display the generated **database password** and **SECRET\_KEY** at the end. You should store these securely.

## Customization

* **REMOTE\_USER** and **SSH\_TARGET** are hardcoded in the script as `philipp@<REMOTE_IP>`. Modify if your server username or host differs.
* **APP\_DIR** (`/opt/zoo_tracker`) and **WEB\_ROOT** (`/var/www/zootracker`) can be changed in the script to suit your environment.
* Edit `zoo_tracker.service` or `zoo_tracker.nginx` templates if you need extra configuration (logging paths, worker counts, SSL settings, etc.).

## Troubleshooting

* **Systemd service fails**: Check `journalctl -u zoo_tracker -e` on the server.
* **nginx errors**: Run `sudo nginx -t` and inspect `/var/log/nginx/error.log`.
* **Certificate issues**: Ensure DNS for `<DOMAIN>` points to `<REMOTE_IP>` before requesting with Certbot.


