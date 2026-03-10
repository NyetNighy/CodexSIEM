# External Access Guide (Subdomain + SSL Certificate)

Use this guide to expose CodexSIEM securely outside localhost.

## Goal

Serve CodexSIEM on a subdomain like `siem.yourdomain.com` over HTTPS with a valid SSL/TLS certificate.

## 1) DNS: create a subdomain

In your DNS provider, create an `A` record:

- **Host/Name**: `siem`
- **Type**: `A`
- **Value**: your public IP

Resulting URL: `https://siem.yourdomain.com`

If you use dynamic public IP, use a dynamic DNS workflow or a cloud load balancer with static IP.

## 2) Run CodexSIEM locally on private interface

Run app internally (example):

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Keep it private and let the reverse proxy handle internet traffic + TLS.

## 3) Put a reverse proxy in front (recommended)

### Option A: Caddy (automatic Let's Encrypt certificates)

Install Caddy and create a Caddyfile:

```caddy
siem.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy automatically provisions and renews certificates.

### Option B: Nginx + Certbot

Install Nginx and Certbot, then configure site:

```nginx
server {
    listen 80;
    server_name siem.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then run Certbot to issue cert and enforce HTTPS redirect.

## 4) Firewall and network controls

- Allow inbound only `443/tcp` (and temporarily `80/tcp` for initial cert issuance if needed).
- Block direct public access to app port (`8000`).
- Restrict access by source IP (office/VPN) when possible.

## 5) App security checklist for external use

- Set strong `SIEM_SESSION_SECRET`.
- Use strong admin password; rotate credentials.
- Use RBAC roles (`admin`, `manager`, `user`) for least privilege.
- Backup `siem.db` securely.

## 6) Verify

- `https://siem.yourdomain.com` loads with a trusted certificate.
- Browser shows a valid lock icon.
- HTTP (`http://`) redirects to HTTPS.

## Notes

- In production, prefer running Uvicorn/Gunicorn as a service (systemd/container).
- Consider adding WAF, fail2ban, and central log monitoring for hardened deployments.

## 7) If enabling SSO header integration

If you enable `SIEM_SSO_ENABLED=true`, make sure header claims are only injected by your trusted reverse proxy/identity gateway.

- Do **not** expose Uvicorn directly to the internet when SSO headers are used.
- Strip incoming client-supplied auth headers and re-add trusted ones at the proxy.
- Recommended headers:
  - `X-Auth-Request-User`
  - `X-Auth-Request-Role`
  - `X-Auth-Request-Amr` (must contain `mfa` when MFA is required)

