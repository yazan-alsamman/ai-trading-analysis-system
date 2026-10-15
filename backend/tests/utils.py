DEFAULT_PASSWORD = "Passw0rd123"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
