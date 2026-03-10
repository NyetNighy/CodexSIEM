from typing import Any, Dict, List


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

    return reasons
