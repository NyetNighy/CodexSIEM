import csv
import io
import logging
import json
import smtplib
import traceback
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateSyntaxError
from starlette.middleware.sessions import SessionMiddleware

from auth import get_admin_credentials, hash_password, verify_password
from secret_utils import ENV_REF_PLACEHOLDER, resolve_client_secret
from siem_core import alert_reasons

DB_PATH = os.getenv("SIEM_DB_PATH", "siem.db")
SYNC_MINUTES = int(os.getenv("SIEM_SYNC_MINUTES", "15"))
APP_TITLE = "M365 Multi-Tenant SIEM"
SESSION_SECRET = os.getenv("SIEM_SESSION_SECRET", "change-me-in-production")
SESSION_HTTPS_ONLY = os.getenv("SIEM_SESSION_HTTPS_ONLY", "false").lower() == "true"
OPENCLAWAI_ENABLED = os.getenv("OPENCLAWAI_ENABLED", "false").lower() == "true"
OPENCLAWAI_URL = os.getenv("OPENCLAWAI_URL", "").strip()
OPENCLAWAI_API_KEY = os.getenv("OPENCLAWAI_API_KEY", "").strip()
OPENCLAWAI_TIMEOUT = float(os.getenv("OPENCLAWAI_TIMEOUT", "10"))

ALERT_EMAIL_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
SMTP_TO = [x.strip() for x in os.getenv("SMTP_TO", "").split(",") if x.strip()]
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

SSO_ENABLED = os.getenv("SIEM_SSO_ENABLED", "false").lower() == "true"
SSO_USER_HEADER = os.getenv("SIEM_SSO_USER_HEADER", "X-Auth-Request-User")
SSO_ROLE_HEADER = os.getenv("SIEM_SSO_ROLE_HEADER", "X-Auth-Request-Role")
SSO_MFA_HEADER = os.getenv("SIEM_SSO_MFA_HEADER", "X-Auth-Request-Amr")
SSO_REQUIRE_MFA = os.getenv("SIEM_SSO_REQUIRE_MFA", "true").lower() == "true"

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_USER}

app = FastAPI(title=APP_TITLE)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=SESSION_HTTPS_ONLY)
templates = Jinja2Templates(directory="templates")
LOGGER = logging.getLogger(__name__)


def startup_template_self_check() -> None:
    template_names = [name for name in templates.env.list_templates() if name.endswith(".html")]
    failed_templates: list[str] = []

    for template_name in template_names:
        try:
            templates.env.get_template(template_name)
        except TemplateSyntaxError as exc:
            failure = f"{template_name}:{exc.lineno}"
            failed_templates.append(failure)
            LOGGER.exception(
                "Template syntax error during startup check for %s (file=%s, line=%s): %s",
                template_name,
                exc.filename or template_name,
                exc.lineno,
                exc.message,
            )
        except Exception:  # noqa: BLE001
            failed_templates.append(template_name)
            LOGGER.exception("Template compilation failed during startup for %s", template_name)

    if failed_templates:
        failures = ", ".join(sorted(failed_templates))
        raise RuntimeError(f"Template startup self-check failed for: {failures}")

    LOGGER.info("Template startup self-check passed for %d HTML templates", len(template_names))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=True)
templates = Jinja2Templates(directory="templates")


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(db_conn()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                customer_name TEXT NOT NULL DEFAULT 'Unassigned',
                tenant_id TEXT NOT NULL UNIQUE,
                client_id TEXT NOT NULL,
                client_secret TEXT NOT NULL,
                client_secret_ref TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                graph_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                user_principal_name TEXT,
                ip_address TEXT,
                app_display_name TEXT,
                status_error_code INTEGER,
                status_failure_reason TEXT,
                conditional_access_status TEXT,
                location_country TEXT,
                location_city TEXT,
                raw_json TEXT NOT NULL,
                UNIQUE(tenant_id, graph_id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                signins_graph_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                CHECK(role IN ('admin', 'manager', 'user'))
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                outcome TEXT NOT NULL,
                source_ip TEXT,
                details TEXT
            );
            """
        )
        conn.commit()

        cols = [row[1] for row in conn.execute("PRAGMA table_info(tenants)").fetchall()]
        if "client_secret_ref" not in cols:
            conn.execute("ALTER TABLE tenants ADD COLUMN client_secret_ref TEXT")
        if "customer_name" not in cols:
            conn.execute("ALTER TABLE tenants ADD COLUMN customer_name TEXT NOT NULL DEFAULT 'Unassigned'")

        signins_cols = [row[1] for row in conn.execute("PRAGMA table_info(signins)").fetchall()]
        if "location_country" not in signins_cols:
            conn.execute("ALTER TABLE signins ADD COLUMN location_country TEXT")
        if "location_city" not in signins_cols:
            conn.execute("ALTER TABLE signins ADD COLUMN location_city TEXT")

        conn.commit()


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def has_users() -> bool:
    with closing(db_conn()) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def user_can_manage(role: str) -> bool:
    return role in {ROLE_ADMIN, ROLE_MANAGER}


def user_is_admin(role: str) -> bool:
    return role == ROLE_ADMIN


def audit_log(
    actor: str,
    actor_role: str,
    action: str,
    outcome: str,
    target: str = "",
    source_ip: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    with closing(db_conn()) as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (event_time, actor, actor_role, action, target, outcome, source_ip, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now_iso(),
                actor or "unknown",
                actor_role or "unknown",
                action,
                target,
                outcome,
                source_ip,
                json.dumps(details or {}, ensure_ascii=False),
            ),
        )
        conn.commit()


def maybe_session_from_sso(request: Request) -> None:
    if not SSO_ENABLED:
        return
    if request.session.get("user") and request.session.get("role"):
        return

    user = request.headers.get(SSO_USER_HEADER, "").strip()
    role = request.headers.get(SSO_ROLE_HEADER, ROLE_USER).strip().lower() or ROLE_USER
    amr = request.headers.get(SSO_MFA_HEADER, "").lower()

    if not user:
        return
    if role not in ALLOWED_ROLES:
        role = ROLE_USER

    if SSO_REQUIRE_MFA and "mfa" not in amr:
        audit_log(user, role, "sso_login", "denied", source_ip=request.client.host if request.client else "", details={"reason": "mfa_not_present"})
        return

    request.session["user"] = user
    request.session["role"] = role
    audit_log(user, role, "sso_login", "success", source_ip=request.client.host if request.client else "")


def require_login(request: Request) -> Optional[RedirectResponse]:
    if not has_users():
        return RedirectResponse(url="/setup", status_code=303)

    maybe_session_from_sso(request)
    if request.session.get("user") and request.session.get("role"):
        return None
    return RedirectResponse(url="/login", status_code=303)


def require_manage_access(request: Request) -> Optional[RedirectResponse]:
    auth = require_login(request)
    if auth:
        return auth
    if user_can_manage(request.session.get("role", "")):
        return None
    return RedirectResponse(url="/?error=Insufficient+permissions", status_code=303)


def require_admin_access(request: Request) -> Optional[RedirectResponse]:
    auth = require_login(request)
    if auth:
        return auth
    if user_is_admin(request.session.get("role", "")):
        return None
    return RedirectResponse(url="/?error=Admin+access+required", status_code=303)


def bootstrap_admin_user() -> None:
    admin_user, salt_hex, digest_hex = get_admin_credentials()
    if not salt_hex or not digest_hex:
        return

    with closing(db_conn()) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing == 0:
            conn.execute(
                """
                INSERT INTO users (username, role, password_salt, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_user, ROLE_ADMIN, salt_hex, digest_hex, utc_now_iso()),
            )
            conn.commit()


async def graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]


async def fetch_signins(token: str, lookback_minutes: int = 60) -> List[Dict[str, Any]]:
    since = (datetime.now(tz=timezone.utc) - timedelta(minutes=lookback_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://graph.microsoft.com/v1.0/auditLogs/signIns"
    params = {"$filter": f"createdDateTime ge {since}", "$top": "100"}
    headers = {"Authorization": f"Bearer {token}"}
    records: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30) as client:
        next_url: Optional[str] = url
        while next_url:
            response = await client.get(next_url, headers=headers, params=params if next_url == url else None)
            response.raise_for_status()
            page = response.json()
            records.extend(page.get("value", []))
            next_url = page.get("@odata.nextLink")

    return records


def render_alert_email_html(context: Dict[str, Any]) -> str:
    try:
        template = templates.env.get_template("alert_email.html")
        return template.render(**context)
    except Exception:
        return ""
    template = templates.env.get_template("alert_email.html")
    return template.render(**context)


def send_alert_email(subject: str, body: str, html_body: str = "") -> None:
    if not ALERT_EMAIL_ENABLED:
        return
    if not SMTP_HOST or not SMTP_FROM or not SMTP_TO:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(SMTP_TO)
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        return


def send_openclawai_alert(payload: Dict[str, Any]) -> None:
    if not OPENCLAWAI_ENABLED or not OPENCLAWAI_URL:
        return
    headers = {"Content-Type": "application/json"}
    if OPENCLAWAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENCLAWAI_API_KEY}"
    try:
        httpx.post(OPENCLAWAI_URL, json=payload, headers=headers, timeout=OPENCLAWAI_TIMEOUT)
    except Exception:
        return


def add_impossible_travel_reason(conn: sqlite3.Connection, tenant_id: str, signin: Dict[str, Any]) -> List[str]:
    upn = signin.get("userPrincipalName")
    created = signin.get("createdDateTime")
    location = signin.get("location") or {}
    country = (location.get("countryOrRegion") or "").strip()
    if not upn or not created or not country:
        return []

    row = conn.execute(
        """
        SELECT created_at, location_country
        FROM signins
        WHERE tenant_id = ? AND user_principal_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (tenant_id, upn),
    ).fetchone()
    if not row or not row["location_country"]:
        return []

    try:
        prev_time = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
        cur_time = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except ValueError:
        return []

    if row["location_country"] != country and abs((cur_time - prev_time).total_seconds()) < 3600:
        return [
            f"Possible impossible travel: user moved from {row['location_country']} to {country} within 60 minutes"
        ]
    return []


def persist_signins_and_alerts(tenant_id: str, signins: List[Dict[str, Any]]) -> int:
    ingested = 0
    with closing(db_conn()) as conn:
        customer_row = conn.execute("SELECT customer_name FROM tenants WHERE tenant_id = ?", (tenant_id,)).fetchone()
        customer_name = customer_row["customer_name"] if customer_row and customer_row["customer_name"] else "Unassigned"

        for signin in signins:
            graph_id = signin.get("id")
            if not graph_id:
                continue

            status = signin.get("status") or {}
            location = signin.get("location") or {}
            try:
                conn.execute(
                    """
                    INSERT INTO signins (
                        tenant_id, graph_id, created_at, user_principal_name, ip_address,
                        app_display_name, status_error_code, status_failure_reason,
                        conditional_access_status, location_country, location_city, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant_id,
                        graph_id,
                        signin.get("createdDateTime"),
                        signin.get("userPrincipalName"),
                        signin.get("ipAddress"),
                        signin.get("appDisplayName"),
                        status.get("errorCode"),
                        status.get("failureReason"),
                        signin.get("conditionalAccessStatus"),
                        location.get("countryOrRegion"),
                        location.get("city"),
                        str(signin),
                    ),
                )
                ingested += 1
            except sqlite3.IntegrityError:
                continue

            reasons = alert_reasons(signin)
            reasons.extend(add_impossible_travel_reason(conn, tenant_id, signin))

            for reason in reasons:
                severity = "high" if any(x in reason for x in ["Failed", "Risk", "impossible travel"]) else "medium"
                created_at = utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO alerts (tenant_id, signins_graph_id, severity, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tenant_id, graph_id, severity, reason, created_at),
                )
                payload = {
                    "source": "codexsiem",
                    "tenant_id": tenant_id,
                    "customer_name": customer_name,
                    "signins_graph_id": graph_id,
                    "severity": severity,
                    "reason": reason,
                    "created_at": created_at,
                    "user_principal_name": signin.get("userPrincipalName"),
                    "ip_address": signin.get("ipAddress"),
                    "app_display_name": signin.get("appDisplayName"),
                    "signin_time": signin.get("createdDateTime"),
                    "status": signin.get("status") or {},
                }
                send_openclawai_alert(payload)
                send_alert_email(
                    subject=f"[CodexSIEM] {severity.upper()} alert for {tenant_id}",
                    body=(
                        f"Customer: {customer_name}\n"
                        f"Tenant: {tenant_id}\n"
                        f"User: {signin.get('userPrincipalName')}\n"
                        f"IP: {signin.get('ipAddress')}\n"
                        f"App: {signin.get('appDisplayName')}\n"
                        f"Reason: {reason}\n"
                        f"Time: {created_at}"
                    ),
                )

        conn.commit()
    return ingested


async def sync_all_tenants() -> Dict[str, Any]:
    results = {"tenants": 0, "ingested": 0, "errors": []}
    with closing(db_conn()) as conn:
        tenants = conn.execute("SELECT * FROM tenants ORDER BY name ASC").fetchall()

    for tenant in tenants:
        results["tenants"] += 1
        try:
            secret = resolve_client_secret(tenant)
            if not secret:
                raise ValueError(f"Missing client secret. Set env var '{tenant['client_secret_ref']}' or update tenant config.")
            token = await graph_token(tenant["tenant_id"], tenant["client_id"], secret)
            signins = await fetch_signins(token, lookback_minutes=SYNC_MINUTES)
            results["ingested"] += persist_signins_and_alerts(tenant["tenant_id"], signins)
        except Exception as exc:  # noqa: BLE001
            results["errors"].append(f"{tenant['name']}: {exc}")
    return results


@app.on_event("startup")
async def startup() -> None:
    startup_template_self_check()
    init_db()
    bootstrap_admin_user()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace = traceback.format_exc()
    try:
        audit_log(
            actor=request.session.get("user", "anonymous") if hasattr(request, "session") else "anonymous",
            actor_role=request.session.get("role", "unknown") if hasattr(request, "session") else "unknown",
            action="unhandled_exception",
            outcome="error",
            source_ip=request.client.host if request.client else "",
            details={"error": str(exc), "trace": trace[-4000:]},
        )
    except Exception:
        pass

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "An internal error occurred. Check audit logs."},
            status_code=500,
        )

    return RedirectResponse(url="/?error=Internal+server+error", status_code=303)


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, error: str = "") -> HTMLResponse:
    if has_users():
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("setup.html", {"request": request, "error": error})


@app.post("/setup")
async def setup_first_admin(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
) -> RedirectResponse:
    if has_users():
        return RedirectResponse(url="/login", status_code=303)

    pwd = password.strip()
    cpwd = confirm_password.strip()
    if not pwd or pwd != cpwd:
        return RedirectResponse(url="/setup?error=Passwords+do+not+match", status_code=303)

    salt_hex, digest_hex = hash_password(pwd)
    with closing(db_conn()) as conn:
        conn.execute(
            """
            INSERT INTO users (username, role, password_salt, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Admin", ROLE_ADMIN, salt_hex, digest_hex, utc_now_iso()),
        )
        conn.commit()

    request.session["user"] = "Admin"
    request.session["role"] = ROLE_ADMIN
    audit_log("Admin", ROLE_ADMIN, "first_admin_setup", "success", source_ip=request.client.host if request.client else "")
    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "") -> HTMLResponse:
    if not has_users():
        return RedirectResponse(url="/setup", status_code=303)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "") -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    if not has_users():
        return RedirectResponse(url="/setup", status_code=303)

    ip = request.client.host if request.client else ""
    with closing(db_conn()) as conn:
        row = conn.execute(
            "SELECT username, role, password_salt, password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

    if not row:
        audit_log(username.strip(), "unknown", "login", "failed", source_ip=ip)
        return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)

    if verify_password(password, row["password_salt"], row["password_hash"]):
        request.session["user"] = row["username"]
        request.session["role"] = row["role"]
        audit_log(row["username"], row["role"], "login", "success", source_ip=ip)
        return RedirectResponse(url="/", status_code=303)

    audit_log(row["username"], row["role"], "login", "failed", source_ip=ip)
    return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    audit_log(request.session.get("user", "unknown"), request.session.get("role", "unknown"), "logout", "success", source_ip=request.client.host if request.client else "")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, q: str = "", error: str = "") -> HTMLResponse:
    auth_redirect = require_login(request)
    if auth_redirect:
        return auth_redirect

    query = q.strip()
    with closing(db_conn()) as conn:
        tenant_count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
        signin_count = conn.execute("SELECT COUNT(*) FROM signins").fetchone()[0]
        alert_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

        filters = ""
        params: List[Any] = []
        if query:
            filters = "WHERE s.tenant_id LIKE ? OR t.customer_name LIKE ? OR s.user_principal_name LIKE ? OR s.ip_address LIKE ? OR s.app_display_name LIKE ?"
            term = f"%{query}%"
            params = [term, term, term, term, term]

        rows = conn.execute(
            f"""
            SELECT a.created_at AS alerted_at, a.severity, a.reason,
                   s.tenant_id, t.customer_name, s.user_principal_name, s.ip_address,
                   s.app_display_name, s.created_at AS signin_time,
                   s.status_error_code, s.status_failure_reason
            FROM alerts a
            JOIN signins s ON s.graph_id = a.signins_graph_id AND s.tenant_id = a.tenant_id
            JOIN tenants t ON t.tenant_id = s.tenant_id
            {filters}
            ORDER BY a.created_at DESC
            LIMIT 200
            """,
            params,
        ).fetchall()

    role = request.session.get("role", "")
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tenant_count": tenant_count,
            "signin_count": signin_count,
            "alert_count": alert_count,
            "alerts": rows,
            "q": query,
            "error": error,
            "user": request.session.get("user", ""),
            "role": role,
            "can_manage": user_can_manage(role),
            "is_admin": user_is_admin(role),
        },
    )


@app.get("/export/alerts.csv")
async def export_alerts_csv(request: Request, q: str = "") -> StreamingResponse:
    auth_redirect = require_login(request)
    if auth_redirect:
        # Not ideal for file endpoints, but keeps auth behavior consistent.
        return StreamingResponse(iter(["Unauthorized"]), status_code=401)

    query = q.strip()
    with closing(db_conn()) as conn:
        filters = ""
        params: List[Any] = []
        if query:
            filters = "WHERE s.tenant_id LIKE ? OR t.customer_name LIKE ? OR s.user_principal_name LIKE ? OR s.ip_address LIKE ? OR s.app_display_name LIKE ?"
            term = f"%{query}%"
            params = [term, term, term, term, term]

        rows = conn.execute(
            f"""
            SELECT a.created_at AS alerted_at, t.customer_name, s.tenant_id,
                   s.user_principal_name, s.ip_address, s.app_display_name,
                   s.created_at AS signin_time, a.severity, a.reason,
                   s.status_error_code, s.status_failure_reason
            FROM alerts a
            JOIN signins s ON s.graph_id = a.signins_graph_id AND s.tenant_id = a.tenant_id
            JOIN tenants t ON t.tenant_id = s.tenant_id
            {filters}
            ORDER BY a.created_at DESC
            LIMIT 5000
            """,
            params,
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "alerted_at",
        "customer_name",
        "tenant_id",
        "user_principal_name",
        "ip_address",
        "app_display_name",
        "signin_time",
        "severity",
        "reason",
        "status_error_code",
        "status_failure_reason",
    ])
    for row in rows:
        writer.writerow([
            row["alerted_at"],
            row["customer_name"],
            row["tenant_id"],
            row["user_principal_name"],
            row["ip_address"],
            row["app_display_name"],
            row["signin_time"],
            row["severity"],
            row["reason"],
            row["status_error_code"],
            row["status_failure_reason"],
        ])

    csv_data = output.getvalue()
    output.close()

    filename = "codexsiem_alerts.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter([csv_data]), media_type="text/csv", headers=headers)



@app.get("/tenants", response_class=HTMLResponse)
async def tenant_page(request: Request) -> HTMLResponse:
    auth_redirect = require_manage_access(request)
    if auth_redirect:
        return auth_redirect

    with closing(db_conn()) as conn:
        tenants = conn.execute("SELECT name, customer_name, tenant_id, client_id, client_secret_ref, created_at FROM tenants ORDER BY customer_name ASC, name ASC").fetchall()
    return templates.TemplateResponse(
        "tenants.html",
        {
            "request": request,
            "tenants": tenants,
            "user": request.session.get("user", ""),
            "role": request.session.get("role", ""),
        },
    )


@app.post("/tenants")
async def create_tenant(
    request: Request,
    name: str = Form(...),
    customer_name: str = Form(...),
    tenant_id: str = Form(...),
    client_id: str = Form(...),
    client_secret_ref: str = Form(...),
) -> RedirectResponse:
    auth_redirect = require_manage_access(request)
    if auth_redirect:
        return auth_redirect

    secret_ref = client_secret_ref.strip()
    if not secret_ref:
        return RedirectResponse(url="/tenants", status_code=303)

    with closing(db_conn()) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tenants (name, customer_name, tenant_id, client_id, client_secret, client_secret_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name.strip(), customer_name.strip() or "Unassigned", tenant_id.strip(), client_id.strip(), ENV_REF_PLACEHOLDER, secret_ref, utc_now_iso()),
        )
        conn.commit()

    audit_log(request.session.get("user", "unknown"), request.session.get("role", "unknown"), "tenant_upsert", "success", target=tenant_id, source_ip=request.client.host if request.client else "", details={"customer_name": customer_name.strip() or "Unassigned"})
    return RedirectResponse(url="/tenants", status_code=303)


@app.post("/sync")
async def trigger_sync(request: Request) -> RedirectResponse:
    auth_redirect = require_manage_access(request)
    if auth_redirect:
        return auth_redirect

    results = await sync_all_tenants()
    audit_log(request.session.get("user", "unknown"), request.session.get("role", "unknown"), "sync", "success" if not results["errors"] else "partial", source_ip=request.client.host if request.client else "", details=results)
    return RedirectResponse(url="/", status_code=303)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request) -> HTMLResponse:
    auth_redirect = require_admin_access(request)
    if auth_redirect:
        return auth_redirect

    with closing(db_conn()) as conn:
        users = conn.execute("SELECT username, role, created_at FROM users ORDER BY created_at ASC").fetchall()

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "user": request.session.get("user", ""),
            "role": request.session.get("role", ""),
            "allowed_roles": sorted(ALLOWED_ROLES),
        },
    )


@app.post("/users")
async def create_or_update_user(
    request: Request,
    username: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    auth_redirect = require_admin_access(request)
    if auth_redirect:
        return auth_redirect

    normalized_role = role.strip().lower()
    if normalized_role not in ALLOWED_ROLES:
        return RedirectResponse(url="/users", status_code=303)

    uname = username.strip()
    pwd = password.strip()
    if not uname or not pwd:
        return RedirectResponse(url="/users", status_code=303)

    salt_hex, digest_hex = hash_password(pwd)

    with closing(db_conn()) as conn:
        conn.execute(
            """
            INSERT INTO users (username, role, password_salt, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                role=excluded.role,
                password_salt=excluded.password_salt,
                password_hash=excluded.password_hash
            """,
            (uname, normalized_role, salt_hex, digest_hex, utc_now_iso()),
        )
        conn.commit()

    audit_log(request.session.get("user", "unknown"), request.session.get("role", "unknown"), "user_upsert", "success", target=uname, source_ip=request.client.host if request.client else "", details={"assigned_role": normalized_role})
    return RedirectResponse(url="/users", status_code=303)


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request) -> HTMLResponse:
    auth_redirect = require_admin_access(request)
    if auth_redirect:
        return auth_redirect

    with closing(db_conn()) as conn:
        logs = conn.execute(
            """
            SELECT event_time, actor, actor_role, action, target, outcome, source_ip, details
            FROM audit_logs
            ORDER BY id DESC
            LIMIT 300
            """
        ).fetchall()

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "logs": logs,
            "user": request.session.get("user", ""),
            "role": request.session.get("role", ""),
        },
    )
