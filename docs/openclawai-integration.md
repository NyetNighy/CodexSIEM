# OpenClawAI Integration (Optional)

CodexSIEM can optionally forward generated alerts to an OpenClawAI-compatible HTTP endpoint.

## Configure

Set these environment variables where CodexSIEM runs:

- `OPENCLAWAI_ENABLED=true`
- `OPENCLAWAI_URL=https://your-openclawai.example/api/alerts`
- `OPENCLAWAI_API_KEY=<token>` (optional)
- `OPENCLAWAI_TIMEOUT=10` (optional timeout seconds)

## Payload example

CodexSIEM sends JSON like:

```json
{
  "source": "codexsiem",
  "tenant_id": "<tenant-guid>",
  "signins_graph_id": "<graph-signin-id>",
  "severity": "high",
  "reason": "Failed sign-in (error code 50058)",
  "created_at": "2026-03-10T11:00:00+00:00",
  "user_principal_name": "user@tenant.com",
  "ip_address": "203.0.113.10",
  "app_display_name": "Office 365 Exchange Online",
  "signin_time": "2026-03-10T10:59:30Z",
  "status": {
    "errorCode": 50058,
    "failureReason": "Interrupted"
  }
}
```

## Notes

- Delivery is best-effort and non-blocking.
- If OpenClawAI is down or returns errors, SIEM ingestion still proceeds.
- Use HTTPS endpoints and API tokens for secure transport/authentication.
