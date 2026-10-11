"""Read-only Microsoft Graph sign-in for outlook.com (personal Microsoft accounts).

One-time sign-in with a device code (no password is stored):

    uv run python -m mail_agent.auth outlook --alias personal

The MSAL token cache is written to ``.mafx/secrets/mail/outlook-<alias>.bin`` (mode 600). Tools then refresh the
access token silently with :func:`get_access_token`.

Configuration (environment / .env):
    MAIL_OUTLOOK_CLIENT_ID   Application (client) id of the ``mafx-mail`` app registration (see the project README).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import msal

AUTHORITY = "https://login.microsoftonline.com/consumers"
# Read access only. MSAL adds offline_access (refresh token), openid and profile itself and refuses them as input.
SCOPES = ["Mail.Read"]
CLIENT_ID_ENV = "MAIL_OUTLOOK_CLIENT_ID"

# Tests inject a fake MSAL http client here; None means MSAL's default (requests).
_http_client: Any | None = None

_ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class AuthError(RuntimeError):
    """Raised with a message meant for the user or the model (it is returned as the tool error)."""


def sign_in_hint(alias: str) -> str:
    return f"run: uv run python -m mail_agent.auth outlook --alias {alias}"


def secrets_dir() -> Path:
    from maf_labs_host import find_workspace

    try:
        root = find_workspace(Path(__file__)).root
    except Exception:
        root = Path.cwd()
    return root / ".mafx" / "secrets" / "mail"


def cache_path(alias: str) -> Path:
    if not _ALIAS_RE.match(alias):
        raise AuthError(f"invalid account alias '{alias}' (letters, digits, '-' and '_' only)")
    return secrets_dir() / f"outlook-{alias}.bin"


def _client_id() -> str:
    value = os.environ.get(CLIENT_ID_ENV, "").strip()
    if not value:
        raise AuthError(f"{CLIENT_ID_ENV} is not set; add the app registration's client id to .env (see README)")
    return value


def _load_cache(path: Path) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if path.is_file():
        cache.deserialize(path.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache, path: Path) -> None:
    if not cache.has_state_changed:
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(cache.serialize())
    os.chmod(path, 0o600)  # the file may predate this run with looser permissions


def _app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    kwargs: dict[str, Any] = {"authority": AUTHORITY, "token_cache": cache}
    if _http_client is not None:
        kwargs["http_client"] = _http_client
    return msal.PublicClientApplication(_client_id(), **kwargs)


def sign_in(alias: str) -> str:
    """Interactive device code sign-in. Prints the code to stderr; returns the signed-in account name."""
    path = cache_path(alias)
    cache = _load_cache(path)
    app = _app(cache)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise AuthError(f"could not start device code sign-in: {flow.get('error_description') or flow}")
    print(flow["message"], file=sys.stderr, flush=True)
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise AuthError(f"sign-in failed: {result.get('error_description') or result.get('error')}")
    _save_cache(cache, path)
    return (result.get("id_token_claims") or {}).get("preferred_username", alias)


def get_access_token(alias: str) -> str:
    """Access token from the cache, refreshed silently. Never prompts."""
    path = cache_path(alias)
    if not path.is_file():
        raise AuthError(f"no sign-in for account '{alias}'; {sign_in_hint(alias)}")
    cache = _load_cache(path)
    app = _app(cache)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        raise AuthError(f"the sign-in for account '{alias}' expired or is invalid; {sign_in_hint(alias)}")
    _save_cache(cache, path)
    return result["access_token"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mail_agent.auth", description="Sign in to a mail account.")
    parser.add_argument("provider", choices=["outlook"], help="mail provider (outlook.com)")
    parser.add_argument("--alias", required=True, help="short account name, e.g. personal")
    args = parser.parse_args(argv)

    from maf_labs_host.workspace import find_workspace, load_env

    try:
        load_env(find_workspace(Path(__file__)))
    except Exception:
        pass  # no workspace: rely on the process environment
    try:
        who = sign_in(args.alias)
    except AuthError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"signed in as {who}; token cache: {cache_path(args.alias)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
