"""Device code sign-in and silent refresh against a fake MSAL http client (no network)."""

import base64
import json
import stat
from urllib.parse import parse_qs

import pytest
from mail_agent import auth

TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"  # the consumers tenant


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


ID_TOKEN = ".".join(
    [
        _b64({"alg": "none"}),
        _b64(
            {
                "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
                "aud": "client-123",
                "sub": "s",
                "oid": "user-1",
                "tid": TENANT,
                "preferred_username": "jean@outlook.com",
                "exp": 4_102_444_800,
                "iat": 1_700_000_000,
            }
        ),
        "",
    ]
)


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.headers = {"content-type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    """Minimal MSAL http client: OpenID discovery, device code and token endpoints."""

    def __init__(self):
        self.posts: list[tuple[str, dict]] = []
        self.token_grants: list[str] = []

    def get(self, url, params=None, headers=None, **kwargs):
        if "openid-configuration" in url:
            base = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
            return _Response(
                {
                    "authorization_endpoint": f"{base}/authorize",
                    "token_endpoint": f"{base}/token",
                    "device_authorization_endpoint": f"{base}/devicecode",
                    "issuer": "https://login.microsoftonline.com/{tenantid}/v2.0",
                }
            )
        return _Response({"tenant_discovery_endpoint": url, "metadata": []})

    def post(self, url, params=None, data=None, headers=None, **kwargs):
        form = data if isinstance(data, dict) else {k: v[0] for k, v in parse_qs(data or "").items()}
        self.posts.append((url, form))
        if url.endswith("/devicecode"):
            return _Response(
                {
                    "user_code": "ABCD-1234",
                    "device_code": "dev-code",
                    "verification_uri": "https://microsoft.com/devicelogin",
                    "expires_in": 900,
                    "interval": 0,
                    "message": "To sign in, open https://microsoft.com/devicelogin and enter ABCD-1234",
                }
            )
        self.token_grants.append(form.get("grant_type", ""))
        return _Response(
            {
                "token_type": "Bearer",
                "scope": "Mail.Read",
                "expires_in": 3600,
                "access_token": f"access-{len(self.token_grants)}",
                "refresh_token": "refresh-1",
                "id_token": ID_TOKEN,
                "client_info": _b64({"uid": "user-1", "utid": TENANT}),
            }
        )


@pytest.fixture
def fake(monkeypatch, tmp_path):
    http = FakeHttp()
    monkeypatch.setattr(auth, "_http_client", http)
    monkeypatch.setattr(auth, "secrets_dir", lambda: tmp_path / "secrets" / "mail")
    monkeypatch.setenv(auth.CLIENT_ID_ENV, "client-123")
    return http


def test_only_read_access_is_requested(fake, capsys):
    auth.sign_in("personal")
    _, form = next(p for p in fake.posts if p[0].endswith("/devicecode"))
    assert set(form["scope"].split()) == {"Mail.Read", "offline_access", "openid", "profile"}
    assert auth.SCOPES == ["Mail.Read"]
    assert "ABCD-1234" in capsys.readouterr().err  # the code goes to stderr, never stdout


def test_sign_in_writes_cache_with_mode_600(fake, tmp_path):
    assert auth.sign_in("personal") == "jean@outlook.com"
    path = tmp_path / "secrets" / "mail" / "outlook-personal.bin"
    assert path.is_file() and stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "refresh-1" in path.read_text()


def test_access_token_refreshes_silently_from_cache(fake, tmp_path):
    auth.sign_in("personal")
    cached = json.loads((tmp_path / "secrets" / "mail" / "outlook-personal.bin").read_text())
    cached["AccessToken"] = {}  # drop the access token so MSAL must use the refresh token
    (tmp_path / "secrets" / "mail" / "outlook-personal.bin").write_text(json.dumps(cached))
    assert auth.get_access_token("personal") == "access-2"
    assert fake.token_grants[-1] == "refresh_token"


def test_missing_sign_in_tells_how_to_fix(fake):
    with pytest.raises(auth.AuthError, match="python -m mail_agent.auth outlook --alias work"):
        auth.get_access_token("work")


def test_missing_client_id(fake, monkeypatch):
    monkeypatch.delenv(auth.CLIENT_ID_ENV)
    with pytest.raises(auth.AuthError, match="MAIL_OUTLOOK_CLIENT_ID"):
        auth.sign_in("personal")


@pytest.mark.parametrize("alias", ["../x", "a/b", "", "a b"])
def test_alias_cannot_escape_secrets_dir(alias):
    with pytest.raises(auth.AuthError, match="invalid account alias"):
        auth.cache_path(alias)
