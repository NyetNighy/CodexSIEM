from auth import hash_password, verify_password


def test_hash_and_verify_round_trip():
    salt, digest = hash_password("CorrectHorseBatteryStaple")
    assert verify_password("CorrectHorseBatteryStaple", salt, digest)


def test_verify_fails_on_wrong_password():
    salt, digest = hash_password("secret-1")
    assert not verify_password("secret-2", salt, digest)
