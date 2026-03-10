import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from auth import get_admin_credentials, hash_password, verify_password
from siem_core import alert_reasons
from secret_utils import ENV_REF_PLACEHOLDER, resolve_client_secret

DB_PATH = os.getenv("SIEM_DB_PATH", "siem.db")
SYNC_MINUTES = int(os.getenv("SIEM_SYNC_MINUTES", "15"))
APP_TITLE = "M365 Multi-Tenant SIEM"
SESSION_SECRET = os.getenv("SIEM_SESSION_SECRET", "change-me-in-production")
OPENCLAWAI_ENABLED = os.getenv("OPENCLAWAI_ENABLED", "false").lower() == "true"
OPENCLAWAI_URL = os.getenv("OPENCLAWAI_URL", "").strip()
OPENCLAWAI_API_KEY = os.getenv("OPENCLAWAI_API_KEY", "").strip()
OPENCLAWAI_TIMEOUT = float(os.getenv("OPENCLAWAI_TIMEOUT", "10"))

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_USER}

app = FastAPI(title=APP_TITLE)
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
            """
        )
        conn.commit()

        # Backward-compatible migration.
        cols = [row[1] for row in conn.execute("PRAGMA table_info(tenants)").fetchall()]
        if "client_secret_ref" not in cols:
            conn.execute("ALTER TABLE tenants ADD COLUMN client_secret_ref TEXT")
            conn.commit()


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def user_can_manage(role: str) -> bool:
    return role in {ROLE_ADMIN, ROLE_MANAGER}


def user_is_admin(role: str) -> bool:
    return role == ROLE_ADMIN


def require_login(request: Request) -> Optional[RedirectResponse]:
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
        payload = response.json()
        return payload["access_token"]


async def fetch_signins(token: str, lookback_minutes: int = 60) -> List[Dict[str, Any]]:
    since = (datetime.now(tz=timezone.utc) - timedelta(minutes=lookback_minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
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


def persist_signins_and_alerts(tenant_id: str, signins: List[Dict[str, Any]]) -> int:
    ingested = 0
    with closing(db_conn()) as conn:
        for signin in signins:
            graph_id = signin.get("id")
            if not graph_id:
                continue

            status = signin.get("status") or {}
            try:
                conn.execute(
                    """
                    INSERT INTO signins (
                        tenant_id, graph_id, created_at, user_principal_name, ip_address,
                        app_display_name, status_error_code, status_failure_reason,
                        conditional_access_status, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        str(signin),
                    ),
                )
                ingested += 1
            except sqlite3.IntegrityError:
                continue

            for reason in alert_reasons(signin):
                severity = "high" if "Failed" in reason or "Risk" in reason else "medium"
                created_at = utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO alerts (tenant_id, signins_graph_id, severity, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tenant_id, graph_id, severity, reason, created_at),
                )
                send_openclawai_alert(
                    {
                        "source": "codexsiem",
                        "tenant_id": tenant_id,
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
                raise ValueError(
                    f"Missing client secret. Set env var '{tenant['client_secret_ref']}' or update tenant config."
                )
            token = await graph_token(tenant["tenant_id"], tenant["client_id"], secret)
            signins = await fetch_signins(token, lookback_minutes=SYNC_MINUTES)
            results["ingested"] += persist_signins_and_alerts(tenant["tenant_id"], signins)
        except Exception as exc:  # noqa: BLE001
            results["errors"].append(f"{tenant['name']}: {exc}")
    return results


@app.on_event("startup")
async def startup() -> None:
    init_db()
    bootstrap_admin_user()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "") -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    with closing(db_conn()) as conn:
        row = conn.execute(
            "SELECT username, role, password_salt, password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

    if not row:
        return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)

    if verify_password(password, row["password_salt"], row["password_hash"]):
        request.session["user"] = row["username"]
        request.session["role"] = row["role"]
        return RedirectResponse(url="/", status_code=303)

    return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
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
            filters = (
                "WHERE s.tenant_id LIKE ? OR s.user_principal_name LIKE ? OR s.ip_address LIKE ? OR s.app_display_name LIKE ?"
            )
            term = f"%{query}%"
            params = [term, term, term, term]

        rows = conn.execute(
            f"""
            SELECT a.created_at AS alerted_at, a.severity, a.reason,
                   s.tenant_id, s.user_principal_name, s.ip_address,
                   s.app_display_name, s.created_at AS signin_time,
                   s.status_error_code, s.status_failure_reason
            FROM alerts a
            JOIN signins s ON s.graph_id = a.signins_graph_id AND s.tenant_id = a.tenant_id
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


@app.get("/tenants", response_class=HTMLResponse)
async def tenant_page(request: Request) -> HTMLResponse:
    auth_redirect = require_manage_access(request)
    if auth_redirect:
        return auth_redirect

    with closing(db_conn()) as conn:
        tenants = conn.execute(
            "SELECT name, tenant_id, client_id, client_secret_ref, created_at FROM tenants ORDER BY name ASC"
        ).fetchall()
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
            INSERT OR REPLACE INTO tenants (name, tenant_id, client_id, client_secret, client_secret_ref, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name.strip(), tenant_id.strip(), client_id.strip(), ENV_REF_PLACEHOLDER, secret_ref, utc_now_iso()),
        )
        conn.commit()
    return RedirectResponse(url="/tenants", status_code=303)


@app.post("/sync")
async def trigger_sync(request: Request) -> RedirectResponse:
    auth_redirect = require_manage_access(request)
    if auth_redirect:
        return auth_redirect

    await sync_all_tenants()
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

    return RedirectResponse(url="/users", status_code=303)
