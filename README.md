# CodexSIEM

A lightweight **multi-tenant Microsoft 365 SIEM starter** that:

- Connects to multiple M365 tenancies (each with its own Entra app credentials).
- Pulls sign-in logs from Microsoft Graph (`auditLogs/signIns`).
- Generates alerts for suspicious sign-ins (failed attempts, risky sign-ins, conditional-access issues).
- Displays customer, tenancy, user, and sign-in details in a dashboard.
- Supports dashboard search by customer, tenant, user, IP, or app, plus CSV export.
- Supports role-based access control with **admin**, **manager**, and **user** roles.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_server.py --host 0.0.0.0 --port 8000
```

Open in browser: `http://localhost:8000` (not `0.0.0.0`).


### Local login/session note

If you run without HTTPS (typical local dev), keep session secure-cookie mode disabled:

- `SIEM_SESSION_HTTPS_ONLY=false` (default)

If you deploy behind HTTPS, enable it:

- `SIEM_SESSION_HTTPS_ONLY=true`

Using secure-only cookies on plain HTTP can cause login/setup loops or blank/unauthenticated behavior after redirects.

## Microsoft 365 app setup (tenant side)

For a direct tenant-side Entra app registration walkthrough, see:

- [`docs/m365-app-setup.md`](docs/m365-app-setup.md)

## Pull request conflict workflow

If GitHub reports merge conflicts on your PR, follow:

- [`docs/pr-conflicts.md`](docs/pr-conflicts.md)

## Troubleshooting startup: `ModuleNotFoundError: No module named itsdangerous`

If Uvicorn fails at startup with `No module named 'itsdangerous'`, your virtual environment is missing dependencies.

Run:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
# Recommended entrypoint for runtime resilience
# Use `main:app` as the operational ASGI entrypoint (recommended for resilience).
python scripts/verify_runtime.py
```

If that still fails, recreate the venv cleanly:

```bash
deactivate || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Recommended entrypoint for runtime resilience
# Use `main:app` as the operational ASGI entrypoint (recommended for resilience).
python scripts/verify_runtime.py
```

Then retry:

```bash
python run_server.py --host 0.0.0.0 --port 8000
```

If you still want to call Uvicorn directly, run `python scripts/verify_runtime.py` immediately before `uvicorn main:app` to detect stale or malformed local files first.

If you see a syntax error coming from `scripts/run_server.py`, prefer the root wrapper instead:

```bash
python run_server.py --host 0.0.0.0 --port 8000
```

If preflight reports indentation/syntax corruption in `app.py` or `application.py`, you can let the launcher attempt automatic git recovery:

```bash
python run_server.py --auto-recover --host 0.0.0.0 --port 8000
```

## First startup admin setup

If no users exist, the app now redirects to `/setup` and asks for the initial **Admin** account password.

- Username is fixed as `Admin` for first setup.
- After creation, you are signed in automatically.
- You can then create additional admin/manager/user accounts from **Manage Users**.

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

After login as admin, use **Manage Users** to add manager/user accounts. Passwords are entered as plaintext in the UI but hashed server-side before storage.



## CSV export

From the dashboard, use **Export CSV** to download current (or filtered) alerts as `codexsiem_alerts.csv`.

- Endpoint: `/export/alerts.csv`
- Supports search filter via query string: `/export/alerts.csv?q=contoso`

## Alert email notifications

CodexSIEM can send email notifications for generated alerts through SMTP.

Set environment variables:

- `ALERT_EMAIL_ENABLED=true`
- `SMTP_HOST=smtp.example.com`
- `SMTP_PORT=587`
- `SMTP_USER=...` (optional)
- `SMTP_PASSWORD=...` (optional)
- `SMTP_FROM=siem@example.com`
- `SMTP_TO=secops@example.com,soclead@example.com`
- `SMTP_USE_TLS=true`

Behavior:

- Each alert can trigger a multipart email (plain text + HTML) with customer/tenant/user/IP/reason context.
- Email delivery is best-effort and non-blocking (ingestion continues if SMTP is unavailable).

## Customer-to-connection mapping

Each tenant connection can now be tied to a **Customer Name**.

- Use **Customer Name** for the client/account (for example, `Contoso Ltd`).
- Use **Connection Display Name** for your internal connection label (for example, `Contoso-Prod-M365`).
- Dashboard alerts include customer name and search supports customer-based filtering.

## Securing passwords and Microsoft 365 app secrets

This build hardens sensitive data handling:

- User passwords are hashed with PBKDF2-HMAC-SHA256 (salted, non-plaintext storage).
- Tenant client secrets should be stored in environment variables (or an external secret manager) and referenced by variable name in **Manage Tenants**.
- Tenant table stores secret references (e.g., `TENANT_A_CLIENT_SECRET`), not the raw secret values for new/updated tenants.

Example environment variables:

```bash
export TENANT_A_CLIENT_SECRET='super-secret-value'
export TENANT_B_CLIENT_SECRET='another-secret-value'
```

In the tenant form, set `client_secret_ref` to `TENANT_A_CLIENT_SECRET` etc.

## MFA/SSO integration (optional)

You can integrate SSO/MFA using an identity-aware reverse proxy (for example Azure AD + oauth2-proxy) that injects trusted headers.

Environment variables:

- `SIEM_SSO_ENABLED=true`
- `SIEM_SSO_USER_HEADER=X-Auth-Request-User`
- `SIEM_SSO_ROLE_HEADER=X-Auth-Request-Role` (`admin`/`manager`/`user`)
- `SIEM_SSO_MFA_HEADER=X-Auth-Request-Amr`
- `SIEM_SSO_REQUIRE_MFA=true`

Behavior:

- If SSO is enabled and headers are present, CodexSIEM creates a session from those claims.
- If MFA is required and header does not include `mfa`, access is denied and recorded in audit logs.

## Stronger audit logging

CodexSIEM now writes structured security audit records for:

- login success/failure
- SSO login success/denied
- logout
- tenant create/update
- user create/update
- sync operations (including partial failures)

Admin users can view logs at **Audit Logs** in the dashboard (`/audit`).

## Hardened detection logic

Alerting rules now include:

- failed sign-ins
- sign-in risk levels
- conditional access failures/not applied
- legacy auth protocol usage (IMAP/POP/SMTP/EAS/other clients)
- monitored high-risk country codes (`RU`, `KP`, `IR`)
- simple impossible-travel heuristic (country change within 60 minutes)

## Optional OpenClawAI integration

You can forward generated SIEM alerts to an OpenClawAI system via webhook/API endpoint.

Set environment variables:

- `OPENCLAWAI_ENABLED=true`
- `OPENCLAWAI_URL=https://your-openclawai.example/api/alerts`
- `OPENCLAWAI_API_KEY=...` (optional bearer token)
- `OPENCLAWAI_TIMEOUT=10` (seconds, optional)

Behavior:

- Each generated alert is posted as JSON to your OpenClawAI endpoint.
- If OpenClawAI is unavailable, SIEM ingestion continues (non-blocking).

## Microsoft 365 tenant setup guide

For full step-by-step instructions on the Microsoft 365 / Entra ID side (app registration, Graph permissions, consent, and secret creation), see:

- [`docs/m365-setup.md`](docs/m365-setup.md)

## External access with subdomain + SSL certificate

To expose CodexSIEM beyond localhost safely, follow:

- [`docs/external-access.md`](docs/external-access.md)

This covers DNS subdomain setup, reverse proxy, certificate issuance (Let's Encrypt), and firewall hardening.

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

- Customer name
- Tenant ID
- User principal name
- IP address
- Application name

## Notes

- This is a starter implementation; production deployment should add MFA/SSO integration, stronger audit logs, and hardened detection logic.
