import base64


def encode_payload(value: str) -> str:
    raw = (value or "").encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return token


def decode_payload(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    padding = "=" * ((4 - (len(token) % 4)) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    return raw.decode("utf-8", errors="replace")

