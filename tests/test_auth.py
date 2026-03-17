from auth import hash_password, verify_password


def test_hash_and_verify_round_trip():
    salt, digest = hash_password("CorrectHorseBatteryStaple")
    assert verify_password("CorrectHorseBatteryStaple", salt, digest)


def test_verify_fails_on_wrong_password():
    salt, digest = hash_password("secret-1")
    assert not verify_password("secret-2", salt, digest)


def test_hash_password_with_invalid_iteration_env_uses_default(monkeypatch):
    monkeypatch.setenv("SIEM_PBKDF2_ITERATIONS", "not-a-number")
    salt, digest = hash_password("iteration-fallback")
    assert verify_password("iteration-fallback", salt, digest)


def test_hash_password_with_non_positive_iteration_env_uses_default(monkeypatch):
    monkeypatch.setenv("SIEM_PBKDF2_ITERATIONS", "0")
    salt, digest = hash_password("iteration-fallback-positive")
    assert verify_password("iteration-fallback-positive", salt, digest)
