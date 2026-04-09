import os
from typing import Mapping, Optional


ENV_REF_PLACEHOLDER = "__env_ref_required__"


def resolve_client_secret(tenant_row: Mapping[str, str]) -> Optional[str]:
    ref = (tenant_row.get("client_secret_ref") or "").strip()
    if ref:
        return os.getenv(ref, "").strip() or None

    raw = (tenant_row.get("client_secret") or "").strip()
    if raw and raw != ENV_REF_PLACEHOLDER:
        return raw
    return None
