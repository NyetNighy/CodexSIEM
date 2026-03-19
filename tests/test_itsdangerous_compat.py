import time

import itsdangerous


def test_timestamp_signer_roundtrip():
    signer = itsdangerous.TimestampSigner("secret")
    token = signer.sign(b"payload")
    assert signer.unsign(token, max_age=60) == b"payload"


def test_timestamp_signer_expires():
    signer = itsdangerous.TimestampSigner("secret")
    token = signer.sign(b"payload")
    time.sleep(1)
    try:
        signer.unsign(token, max_age=0)
        assert False
    except itsdangerous.SignatureExpired:
        assert True
