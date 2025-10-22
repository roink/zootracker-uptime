# Deploy Directory Instructions

This directory contains automation and configuration assets for provisioning the Zoo Tracker infrastructure with Ansible.

## Layout overview
- `inventory.ini` and `group_vars/` — inventory definitions and shared variables for the `zoo_server` host group.
- `setup-nginx.yml` — full provisioning playbook that bootstraps the myguard repository, installs nginx and compression modules, manages certificates, and deploys the primary configuration.
- `update-nginx-config.yml` — lightweight playbook for re-deploying the nginx templates after edits.
- `templates/` — Jinja2 templates consumed by the playbooks (e.g., nginx.conf, site definitions, ACME challenge config).
- Supporting docs and scripts (e.g., `README.md`, hardening guides) live alongside the playbooks for operator reference.

## Conventions
- Keep Ansible tasks idempotent and prefer built-in modules (`ansible.builtin.*`).
- Use two-space indentation in YAML and Jinja2 templates to match the existing style.
- When modifying nginx templates, ensure TLS and compression modules remain unconditionally loaded, reflecting the assumptions baked into the playbooks.
