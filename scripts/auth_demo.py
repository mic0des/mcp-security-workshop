"""Token-verifier failure demo for workshop Block 2D — MCP07 vulnerability.

Mints three test JWTs locally (no HTTP token endpoint needed — we read
fake_authz_server's private key off disk) and runs each through
PermissiveTokenVerifier, the intentional MCP07 vulnerability in
`acmeops_server.server`.

The punchline: the permissive verifier accepts a JWT minted for
`https://attacker.example` and hands back `scopes=[acme:admin]`.  Every tool
on the server would run as admin for that token holder, even though the token
was never issued for this service.

Run from repo root:
    uv run python scripts/auth_demo.py

To see the fixed behaviour, run:
    uv run python scripts/auth_demo_secure.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import jwt as pyjwt

from acmeops_server.server import PermissiveTokenVerifier

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_KEY_PATH = REPO_ROOT / "fake_authz_server" / "keys" / "private.pem"

ISSUER = "http://localhost:9000"
EXPECTED_AUD = "https://acmeops.internal"
ATTACKER_AUD = "https://attacker.example"
KID = "fake-authz-1"


def _load_private_key() -> str:
    if not PRIVATE_KEY_PATH.exists():
        print(
            f"[fatal] private key not found at {PRIVATE_KEY_PATH}\n"
            "        Start fake_authz_server once to generate it:\n"
            "            uv run python -m fake_authz_server",
            file=sys.stderr,
        )
        sys.exit(1)
    return PRIVATE_KEY_PATH.read_text()


def _mint(private_key: str, *, aud: str, sub: str, scope: str) -> str:
    """Mint an RS256 JWT with the given audience/subject/scope."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": aud,
        "sub": sub,
        "scope": scope,
        "iat": now,
        "exp": now + 600,
        "client_id": "auth-demo-script",
    }
    return pyjwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": KID},
    )


def _format_result(claims: dict[str, Any] | None) -> str:
    if claims is None:
        return "REJECT"
    scopes = claims.get("scopes") or claims.get("scope") or "<no scope>"
    if isinstance(scopes, list):
        scopes = ",".join(scopes)
    return f"ACCEPT [{scopes}]"


async def _verify(verifier: Any, token: str) -> dict[str, Any] | None:
    try:
        return await verifier.verify_token(token)
    except Exception as exc:  # defensive — verifiers should not raise
        return {"_error": repr(exc)}


def _hr(width: int = 78) -> str:
    return "-" * width


async def main() -> None:
    private_key = _load_private_key()

    tokens: dict[str, str] = {
        "empty": "",
        "wrong-aud": _mint(
            private_key,
            aud=ATTACKER_AUD,
            sub="evil@attacker",
            scope="acme:tickets:read",
        ),
        "right-aud": _mint(
            private_key,
            aud=EXPECTED_AUD,
            sub="user-test",
            scope="acme:tickets:read",
        ),
    }

    permissive = PermissiveTokenVerifier()

    print()
    print("Minted three test JWTs:")
    print(f"  empty     : (no credentials at all)")
    print(f"  wrong-aud : aud={ATTACKER_AUD!r}  sub='evil@attacker'")
    print(f"  right-aud : aud={EXPECTED_AUD!r}  sub='user-test'")
    print()
    print("Both are signed with fake_authz_server's RS256 key (kid={!r}).".format(KID))
    print()

    row: dict[str, dict[str, Any] | None] = {}
    for label, token in tokens.items():
        row[label] = await _verify(permissive, token)

    # --- Result row -------------------------------------------------------------
    col_w = 22
    header = (
        f"{'Verifier':<24} | {'empty':<{col_w}} | "
        f"{'wrong-aud':<{col_w}} | {'right-aud':<{col_w}}"
    )
    sep = f"{'-' * 24}-+-{'-' * col_w}-+-{'-' * col_w}-+-{'-' * col_w}"
    cells = [_format_result(row[label]) for label in ("empty", "wrong-aud", "right-aud")]
    print(header)
    print(sep)
    print(
        f"{'PermissiveTokenVerifier':<24} | "
        f"{cells[0]:<{col_w}} | {cells[1]:<{col_w}} | {cells[2]:<{col_w}}"
    )
    print()

    # --- Detail block: show what each ACCEPT actually returned -----------------
    print("Decoded claims for every ACCEPT:")
    print(_hr())
    any_accept = False
    for label, claims in row.items():
        if claims is None:
            continue
        if isinstance(claims, dict) and "_error" in claims:
            continue
        any_accept = True
        print(f"PermissiveTokenVerifier / {label}:")
        for k in ("sub", "aud", "scope", "scopes", "iss", "client_id", "exp"):
            if k in claims:
                print(f"    {k:>10} = {claims[k]!r}")
        print()
    if not any_accept:
        print("  (no tokens were accepted)")
    print(_hr())
    print()

    # --- Punchline --------------------------------------------------------------
    permissive_wrong = row["wrong-aud"]
    print("Punchline")
    print(_hr())
    if permissive_wrong is not None:
        scopes = permissive_wrong.get("scopes") or permissive_wrong.get("scope")
        print(
            "PermissiveTokenVerifier accepted a JWT whose audience claim is\n"
            f"  aud={ATTACKER_AUD!r}\n"
            f"and handed back scopes={scopes!r}.\n"
            "Every tool on this server would execute as admin for that token holder,\n"
            "even though the token was minted for a completely different service.\n"
        )
    else:
        print(
            "(unexpected — PermissiveTokenVerifier should accept any non-empty token)\n"
        )
    print(
        "Fix: implement AcmeTokenVerifier in acmeops_server/server.py and run\n"
        "    uv run python scripts/auth_demo_secure.py\n"
        "to see the wrong-audience token rejected.\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
