import hashlib
import hmac
import os
import secrets

ENV_VAR = "ADMIN_PASSWORD"

_N, _R, _P = 2**14, 8, 1


def env_password() -> str | None:
    value = os.environ.get(ENV_VAR)
    return value or None


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=_N, r=_R, p=_P, dklen=32
    )
    return digest.hex(), salt


def verify(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def generate() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)
    )


def announce(password: str) -> None:
    line = "─" * 52
    print(f"\n┌{line}┐")
    print("│  Első indítás: admin jelszó létrehozva".ljust(53) + "│")
    print("│".ljust(53) + "│")
    print(f"│      {password}".ljust(53) + "│")
    print("│".ljust(53) + "│")
    print("│  Ez csak most jelenik meg. A beállításoknál".ljust(53) + "│")
    print("│  bármikor megváltoztathatod.".ljust(53) + "│")
    print(f"└{line}┘\n", flush=True)
