from typing import Any, Dict, List


LEGACY_AUTH_CLIENTS = {
    "imap4",
    "pop3",
    "smtp",
    "exchange activesync",
    "other clients",
}


def alert_reasons(signin: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    status = signin.get("status") or {}
    err = status.get("errorCode")
    if isinstance(err, int) and err != 0:
        reasons.append(f"Failed sign-in (error code {err})")

    risk_level = signin.get("riskLevelDuringSignIn")
    if risk_level and str(risk_level).lower() not in {"none", "hidden", "null"}:
        reasons.append(f"Risk level during sign-in: {risk_level}")

    cas = signin.get("conditionalAccessStatus")
    if cas and str(cas).lower() in {"failure", "notapplied"}:
        reasons.append(f"Conditional access status: {cas}")

    client_app = str(signin.get("clientAppUsed") or "").lower()
    if client_app in LEGACY_AUTH_CLIENTS:
        reasons.append(f"Legacy authentication client used: {signin.get('clientAppUsed')}")

    location = signin.get("location") or {}
    country = location.get("countryOrRegion")
    if country and str(country).strip().upper() in {"RU", "KP", "IR"}:
        reasons.append(f"Sign-in from monitored high-risk country: {country}")

    return reasons
