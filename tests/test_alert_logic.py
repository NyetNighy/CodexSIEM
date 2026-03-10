from siem_core import alert_reasons


def test_alert_reason_for_failed_signin_and_risk():
    signin = {
        "status": {"errorCode": 50058, "failureReason": "Interrupted"},
        "riskLevelDuringSignIn": "high",
        "conditionalAccessStatus": "success",
    }
    reasons = alert_reasons(signin)
    assert any("Failed sign-in" in r for r in reasons)
    assert any("Risk level" in r for r in reasons)


def test_no_alert_for_clean_signin():
    signin = {
        "status": {"errorCode": 0, "failureReason": ""},
        "riskLevelDuringSignIn": "none",
        "conditionalAccessStatus": "success",
    }
    assert alert_reasons(signin) == []
