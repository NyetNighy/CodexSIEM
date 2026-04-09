# Configure Microsoft 365 / Entra App Registration for CodexSIEM

This guide is focused specifically on the **Microsoft 365 side** (Entra ID / Azure portal) so you can connect a tenant to CodexSIEM.

## 1) Create an Entra app registration

1. Open <https://portal.azure.com> in the tenant you want to onboard.
2. Go to **Microsoft Entra ID** → **App registrations** → **New registration**.
3. Name it (example: `CodexSIEM-Collector`).
4. Select **Accounts in this organizational directory only**.
5. Click **Register**.

Save these values from the overview page:

- **Application (client) ID**
- **Directory (tenant) ID**

## 2) Grant Microsoft Graph Application permissions

1. Open the app registration.
2. Go to **API permissions** → **Add a permission** → **Microsoft Graph**.
3. Choose **Application permissions**.
4. Add:
   - `AuditLog.Read.All` (**required**)
   - `Directory.Read.All` (optional, for extra enrichment)

## 3) Grant admin consent

1. Still on **API permissions**, click **Grant admin consent for <Tenant>**.
2. Confirm all required permissions show **Granted**.

Without this step, Graph calls will fail with authorization errors.

## 4) Create a client secret

1. Go to **Certificates & secrets** → **Client secrets** → **New client secret**.
2. Set description + expiry and click **Add**.
3. Copy the **Secret Value** immediately (not Secret ID).

## 5) Wire values into CodexSIEM

In CodexSIEM:

1. Open dashboard and click **Connect M365 Tenant**.
2. Fill:
   - `Customer Name`
   - `Connection Display Name`
   - `Tenant ID` (Directory ID)
   - `Client ID` (Application ID)
   - `Secret Env Var Name` (example: `TENANT_CONTOSO_SECRET`)
3. Save tenant.

On the CodexSIEM host, set the env var with the real secret value:

```bash
export TENANT_CONTOSO_SECRET='your-secret-value'
```

Then click **Sync Now** on dashboard.

## 6) Verify successful ingestion

- Dashboard tenant count increases.
- Sync completes without permission/secret errors.
- Alerts/sign-in data appears when activity exists.

## Common mistakes

- Using **Secret ID** instead of **Secret Value**.
- Adding **Delegated** permissions instead of **Application** permissions.
- Forgetting **Grant admin consent**.
- Using the wrong tenant context while creating the app registration.
