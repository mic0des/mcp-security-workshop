"""Token-verifier success demo for workshop Block 2D — MCP07 fix.

Mints three test JWTs locally (no HTTP token endpoint needed — we read
fake_authz_server's private key off disk) and runs each through
AcmeTokenVerifier, the audience-validating fix implemented in
`acmeops_server.server`.

The punchline: the audience-checking verifier rejects the JWT minted for
`https://attacker.example` and only accepts the token that was explicitly
issued for `https://acmeops.internal`.  This is the MCP07 fix.

REQUIRES fake_authz_server to be running (it serves the JWKS endpoint):
    uv run python -m fake_authz_server

Run from repo root:
    uv run python scripts/auth_demo_secure.py

To see the vulnerable behaviour first, run:
    uv run python scripts/auth_demo.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import jwt as pyjwt

from acmeops_server.server import AcmeTokenVerifier

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_KEY_PATH = REPO_ROOT / "fake_authz_server" / "keys" / "private.pem"

ISSUER = "http://localhost:9000"
JWKS_URL = "http://localhost:9000/jwks.json"
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

    audience_checked = AcmeTokenVerifier(
        jwks_url=JWKS_URL,
        expected_audience=EXPECTED_AUD,
        expected_issuer=ISSUER,
    )

    print()
    print("Minted three test JWTs:")
    print(f"  empty     : (no credentials at all)")
    print(f"  wrong-aud : aud={ATTACKER_AUD!r}  sub='evil@attacker'")
    print(f"  right-aud : aud={EXPECTED_AUD!r}  sub='user-test'")
    print()
    print("Both are signed with fake_authz_server's RS256 key (kid={!r}).".format(KID))
    print()

    # Probe JWKS reachability up front — fail fast with a clear message.
    print(f"Checking JWKS endpoint at {JWKS_URL} ...")
    try:
        probe = await audience_checked.verify_token(tokens["right-aud"])
        if probe is None:
            raise RuntimeError("verify_token returned None for a valid token")
    except Exception as exc:
        print(
            f"\n[fatal] AcmeTokenVerifier could not reach the JWKS endpoint.\n"
            f"        Error: {exc}\n\n"
            f"        Start fake_authz_server in another terminal first:\n"
            f"            uv run python -m fake_authz_server\n"
            f"        Then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("JWKS endpoint reachable.\n")

    row: dict[str, dict[str, Any] | None] = {}
    for label, token in tokens.items():
        row[label] = await _verify(audience_checked, token)

    # --- Result row -------------------------------------------------------------
    col_w = 22
    header = (
        f"{'Verifier':<24} | {'empty':<{col_w}} | "
        f"{'wrong-aud':<{col_w}} | {'right-aud':<{col_w}}"
    )
    sep = f"{"-" * 24}-+-{"-" * col_w}-+-{"-" * col_w}-+-{"-" * col_w}"
    cells = [_format_result(row[label]) for label in ("empty", "wrong-aud", "right-aud")]
    print(header)
    print(sep)
    print(
        f"{'AcmeTokenVerifier':<24} | "
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
        print(f"AcmeTokenVerifier / {label}:")
        for k in ("sub", "aud", "scope", "scopes", "iss", "client_id", "exp"):
            if k in claims:
                print(f"    {k:>10} = {claims[k]!r}")
        print()
    if not any_accept:
        print("  (no tokens were accepted — check JWKS reachability)")
    print(_hr())
    print()

    # --- Punchline --------------------------------------------------------------
    wrong_result = row["wrong-aud"]
    right_result = row["right-aud"]
    print("Punchline")
    print(_hr())
    if wrong_result is None and right_result is not None:
        scopes = right_result.get("scopes") or right_result.get("scope")
        print(
            "AcmeTokenVerifier rejected the JWT whose audience claim is\n"
            f"  aud={ATTACKER_AUD!r}\n"
            "because it was not issued for this resource server.\n\n"
            "It accepted the correctly-scoped token with\n"
            f"  aud={EXPECTED_AUD!r}\n"
            f"and returned scopes={scopes!r}.\n\n"
            "This is the MCP07 fix in action: audience validation prevents\n"
            "cross-service token replay attacks.\n"
        )
    else:
        print(
            "(unexpected result — verify that fake_authz_server is running\n"
            f" and serving JWKS at {JWKS_URL})\n"
        )


if __name__ == "__main__":
    asyncio.run(main())
