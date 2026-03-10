# CodexSIEM

A lightweight **multi-tenant Microsoft 365 SIEM starter** that:

- Connects to multiple M365 tenancies (each with its own Entra app credentials).
- Pulls sign-in logs from Microsoft Graph (`auditLogs/signIns`).
- Generates alerts for suspicious sign-ins (failed attempts, risky sign-ins, conditional-access issues).
- Displays tenancy, user, and sign-in details in a dashboard.
- Supports dashboard search by tenant, user, IP, or app.
- Supports role-based access control with **admin**, **manager**, and **user** roles.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

## Role-based access (RBAC)

- **admin**: full access (dashboard, sync, tenant management, user management)
- **manager**: manage access (dashboard, sync, tenant management)
- **user**: read-only access (dashboard/search only)

The app stores platform users in a `users` table. On first startup, it can bootstrap one admin account from env vars.

## Bootstrap the first admin

Set these environment variables before first start:

- `SIEM_ADMIN_USERNAME` (example: `siem-admin`)
- `SIEM_ADMIN_SALT` (hex salt)
- `SIEM_ADMIN_PASSWORD_HASH` (PBKDF2-HMAC-SHA256 digest hex)
- `SIEM_SESSION_SECRET` (long random string)

Generate salt/hash from a password:

```bash
python - <<'PY'
from auth import hash_password
salt, digest = hash_password("your-strong-password")
print("SIEM_ADMIN_SALT=", salt)
print("SIEM_ADMIN_PASSWORD_HASH=", digest)
PY
```

After login as admin, use **Manage Users** to add manager/user accounts.


## Microsoft 365 tenant setup guide

For full step-by-step instructions on the Microsoft 365 / Entra ID side (app registration, Graph permissions, consent, and secret creation), see:

- [`docs/m365-setup.md`](docs/m365-setup.md)

## Authentication and secure external access

For secure access from external networks:

1. Put the app behind a reverse proxy with TLS (Nginx, Traefik, Caddy, or cloud LB).
2. Expose only HTTPS (443), do not expose plain HTTP directly.
3. Restrict source IPs where possible (office/VPN ranges).
4. Use strong passwords and rotate `SIEM_SESSION_SECRET` periodically.
5. Store tenant client secrets in a secret manager for production (not plain env vars).

## Required permissions in each M365 tenant

Register an app in each tenant and grant **application permissions**:

- `AuditLog.Read.All`
- `Directory.Read.All` (optional enrichment)

Then grant admin consent and store:

- Tenant ID
- Client ID
- Client Secret

Use **Manage Tenants** in the UI to add each tenancy.

## Sync behavior

- Click **Sync Now** to fetch recent sign-ins.
- Default lookback interval is 15 minutes (`SIEM_SYNC_MINUTES` env var).
- Data is stored in SQLite (`siem.db` by default; override with `SIEM_DB_PATH`).

## Search

The dashboard search box filters alerts by:

- Tenant ID
- User principal name
- IP address
- Application name

## Notes

- This is a starter implementation; production deployment should add MFA/SSO integration, stronger audit logs, and hardened detection logic.
