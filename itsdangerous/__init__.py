from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Union

from .exc import BadSignature, SignatureExpired


class TimestampSigner:
    sep = b"."

    def __init__(self, secret_key: Union[str, bytes], salt: Union[str, bytes] = b"itsdangerous") -> None:
        self.secret_key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
        self.salt = salt.encode("utf-8") if isinstance(salt, str) else salt

    def _timestamp(self) -> bytes:
        return str(int(time.time())).encode("ascii")

    def _get_signature(self, value: bytes, timestamp: bytes) -> bytes:
        msg = value + self.sep + timestamp
        key = self.secret_key + self.salt
        digest = hmac.new(key, msg, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=")

    def sign(self, value: Union[str, bytes]) -> bytes:
        value_bytes = value.encode("utf-8") if isinstance(value, str) else value
        ts = self._timestamp()
        sig = self._get_signature(value_bytes, ts)
        return value_bytes + self.sep + ts + self.sep + sig

    def unsign(self, signed_value: Union[str, bytes], max_age: int | None = None) -> bytes:
        data = signed_value.encode("utf-8") if isinstance(signed_value, str) else signed_value

        try:
            value, ts, sig = data.rsplit(self.sep, 2)
        except ValueError as exc:
            raise BadSignature("Malformed signed value") from exc

        expected = self._get_signature(value, ts)
        if not hmac.compare_digest(sig, expected):
            raise BadSignature("Signature does not match")

        if max_age is not None:
            now = int(time.time())
            try:
                issued = int(ts.decode("ascii"))
            except ValueError as exc:
                raise BadSignature("Invalid timestamp") from exc
            if now - issued > max_age:
                raise SignatureExpired("Signature age exceeded")

        return value


__all__ = ["TimestampSigner", "BadSignature", "SignatureExpired"]
