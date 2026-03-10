# Microsoft 365 (Entra ID) Setup Guide for CodexSIEM

This guide covers everything to configure **on the Microsoft 365 side** so CodexSIEM can read sign-in logs from one or multiple tenants.

## What you are setting up

For each Microsoft 365 tenant you want to monitor, you will:

1. Register an Entra application.
2. Grant Microsoft Graph **Application** permissions.
3. Grant tenant-wide admin consent.
4. Create a client secret.
5. Capture the values needed by CodexSIEM.

You repeat these steps for every additional tenant.

---

## Prerequisites

- You have an account with rights to register apps in the target tenant.
- You have an admin account that can grant consent for Graph app permissions.
- You have CodexSIEM running and admin access to its UI.

---

## Step 1: Register an Entra app (per tenant)

1. Sign in to the Azure portal for the target tenant:
   - <https://portal.azure.com>
2. Go to **Microsoft Entra ID** → **App registrations** → **New registration**.
3. Name the app (example: `CodexSIEM-Collector`).
4. Supported account types:
   - Choose **Accounts in this organizational directory only** for single-tenant setup.
5. Redirect URI is not required for this app-to-app flow.
6. Click **Register**.

After registration, record:

- **Application (client) ID**
- **Directory (tenant) ID**

---

## Step 2: Assign Graph API Application permissions

1. Open the app registration you created.
2. Go to **API permissions** → **Add a permission** → **Microsoft Graph**.
3. Choose **Application permissions** (not Delegated).
4. Add:
   - `AuditLog.Read.All` (required for sign-in logs)
   - `Directory.Read.All` (optional, useful for enrichment)

> Minimum required for current CodexSIEM ingestion is `AuditLog.Read.All`.

---

## Step 3: Grant admin consent

1. Still in **API permissions**, click **Grant admin consent for <TenantName>**.
2. Confirm the action.
3. Verify each permission status shows **Granted for <TenantName>**.

If admin consent is not granted, token calls may work but Graph reads will fail with authorization errors.

---

## Step 4: Create a client secret

1. Go to **Certificates & secrets** → **Client secrets** → **New client secret**.
2. Add description and expiration period.
3. Click **Add**.
4. Copy the **Value** immediately (you cannot retrieve it later).

Record:

- Client secret **Value** (not Secret ID)

---

## Step 5: Add tenant to CodexSIEM

In CodexSIEM (Manager/Admin role):

1. Open **Manage Tenants**.
2. Add:
   - Display Name (friendly label)
   - Tenant ID (Directory ID)
   - Client ID (Application ID)
   - Client Secret (secret value)
3. Save.
4. Use **Sync Now** to test ingestion.

---

## Multi-tenant rollout checklist

Repeat Steps 1–5 for each tenant. Suggested tracker per tenant:

- [ ] Tenant registered app
- [ ] `AuditLog.Read.All` assigned
- [ ] Admin consent granted
- [ ] Secret created and stored securely
- [ ] Tenant added in CodexSIEM
- [ ] Manual sync verified

---

## Troubleshooting

### `Invalid client secret provided`
- Usually the wrong value was used (Secret ID instead of Secret Value), or secret expired.

### `Insufficient privileges to complete the operation`
- Graph permission not granted as **Application** permission or admin consent not completed.

### No sign-ins returned
- Verify logs exist in tenant and time window includes recent sign-ins.
- Check that your tenant has sign-in activity and that app permissions were granted.

### Consent button disabled
- Your account does not have sufficient admin role. Use a Global Admin/Privileged Role Admin as per your org policy.

---

## Security recommendations

- Use a dedicated app registration for SIEM ingestion only.
- Rotate client secrets regularly.
- Store tenant secrets in a secure secret manager (not plain text files).
- Restrict SIEM UI exposure to HTTPS and trusted networks/VPN where possible.

