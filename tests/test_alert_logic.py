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
        "clientAppUsed": "Browser",
        "location": {"countryOrRegion": "US"},
    }
    assert alert_reasons(signin) == []


def test_legacy_auth_and_high_risk_country_detected():
    signin = {
        "status": {"errorCode": 0},
        "clientAppUsed": "IMAP4",
        "location": {"countryOrRegion": "RU"},
    }
    reasons = alert_reasons(signin)
    assert any("Legacy authentication client used" in r for r in reasons)
    assert any("high-risk country" in r for r in reasons)
    }
    assert alert_reasons(signin) == []
