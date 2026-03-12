class BadSignature(Exception):
    """Raised when signed value validation fails."""


class SignatureExpired(BadSignature):
    """Raised when signature is valid but expired."""
